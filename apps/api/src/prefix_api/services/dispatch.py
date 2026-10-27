"""Reminder dispatch: sends due timeline events exactly once.

1. ``claim_due_events`` moves due PENDING events to SENDING in one short transaction, using
   ``FOR UPDATE SKIP LOCKED`` so concurrent dispatchers never claim the same event.
2. ``ReminderSender.send`` handles one claimed event in its own transaction. The Message row
   is written before the provider is called, and a unique index allows only one outbound
   message per event.
3. An event left in SENDING (the worker died mid-send) is marked FAILED after a while rather
   than retried: retrying could send the patient a duplicate. Staff see it and can resend.
"""

import datetime as dt
import uuid
from collections.abc import Callable

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from prefix_api.core.logging import get_logger
from prefix_api.db.models import (
    Appointment,
    CheckIn,
    Message,
    Patient,
    PatientTimelineEvent,
    PrepStep,
)
from prefix_api.domain.enums import (
    AppointmentStatus,
    AuditAction,
    MessageChannel,
    MessageDirection,
    MessageStatus,
    TimelineEventStatus,
)
from prefix_api.domain.principal import SystemPrincipal
from prefix_api.services.audit import record_audit
from prefix_api.services.messaging.base import MessagingError, MessagingProvider, OutboundMessage
from prefix_api.services.translation import SOURCE_LANGUAGE, Translator

logger = get_logger(__name__)

STALE_SENDING_AFTER = dt.timedelta(minutes=15)
CONFIRM_FOOTER = (
    "Reply YES when this is done, NO if you cannot do it, or HELP to talk to your care team."
)
JOB = "reminder_dispatch"

_E = PatientTimelineEvent


def compose_reminder(step: PrepStep) -> str:
    """Reminder text, built only from the clinician-approved step (safety rule a)."""
    text = f"{step.title}\n{step.instruction_text}"
    return f"{text}\n\n{CONFIRM_FOOTER}" if step.requires_confirmation else text


def claim_due_events(session: Session, *, now: dt.datetime, limit: int) -> list[uuid.UUID]:
    ids = list(
        session.scalars(
            select(_E.id)
            .where(_E.status == TimelineEventStatus.PENDING, _E.send_at <= now)
            .order_by(_E.send_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    )
    if ids:
        session.execute(update(_E).where(_E.id.in_(ids)).values(status=TimelineEventStatus.SENDING))
    session.commit()
    return ids


def fail_stale_sends(session: Session, *, now: dt.datetime) -> int:
    result = session.execute(
        update(_E)
        .where(
            _E.status == TimelineEventStatus.SENDING,
            _E.updated_at < now - STALE_SENDING_AFTER,
        )
        .values(
            status=TimelineEventStatus.FAILED,
            last_error="Interrupted while sending; not retried automatically to avoid a duplicate",
        )
        .returning(_E.id)
    )
    count = len(result.all())
    session.commit()
    if count:
        logger.warning("dispatch.stale_sends_failed", count=count)
    return count


def _recipient(patient: Patient, channel: MessageChannel) -> str | None:
    if channel in (MessageChannel.SMS, MessageChannel.WHATSAPP):
        return patient.phone
    if channel is MessageChannel.EMAIL:
        return patient.email
    return None


class ReminderSender:
    def __init__(
        self, session: Session, provider: MessagingProvider, translator: Translator
    ) -> None:
        self._session = session
        self._provider = provider
        self._translator = translator

    def send(self, event_id: uuid.UUID, *, now: dt.datetime) -> TimelineEventStatus | None:
        """Send one claimed event. Returns its final status, or None if it was not ours."""
        session = self._session
        event = session.get(_E, event_id, with_for_update=True)
        if event is None or event.status is not TimelineEventStatus.SENDING:
            session.rollback()
            return None
        appointment = session.get(Appointment, event.appointment_id)
        patient = session.get(Patient, event.patient_id)
        step = session.get(PrepStep, event.step_id)
        if appointment is None or patient is None or step is None:  # pragma: no cover
            return self._finish(event, TimelineEventStatus.FAILED, "Missing records")

        if appointment.status in (AppointmentStatus.CANCELLED, AppointmentStatus.COMPLETED):
            return self._finish(event, TimelineEventStatus.CANCELLED, None)

        principal = SystemPrincipal(organization_id=event.organization_id, job=JOB)
        record_audit(
            session,
            principal=principal,
            action=AuditAction.READ,
            entity_type="patient",
            entity_id=patient.id,
            patient_id=patient.id,
            purpose="prep_reminder",
        )
        if not patient.consent_to_message:
            return self._finish(
                event, TimelineEventStatus.SKIPPED, "Patient has not consented to messages"
            )
        channel = patient.preferred_channel
        to = _recipient(patient, channel)
        if to is None:
            return self._finish(
                event,
                TimelineEventStatus.SKIPPED,
                f"No {channel.value.lower()} contact for this patient",
            )

        original = compose_reminder(step)
        translation = self._translator.translate(original, patient.preferred_language)
        message = Message(
            organization_id=event.organization_id,
            patient_id=patient.id,
            appointment_id=appointment.id,
            timeline_event_id=event.id,
            channel=channel,
            direction=MessageDirection.OUTBOUND,
            status=MessageStatus.QUEUED,
            language=patient.preferred_language if translation.translated else SOURCE_LANGUAGE,
            body=f"Prefix AI: {translation.text}",
            original_body=original if translation.translated else None,
        )
        session.add(message)
        try:
            session.flush()
        except IntegrityError:
            # Another reminder for this event already exists: never send twice.
            session.rollback()
            logger.error("dispatch.duplicate_prevented", event_id=str(event_id))
            return None

        try:
            result = self._provider.send(OutboundMessage(channel=channel, to=to, body=message.body))
        except MessagingError as exc:
            message.status = MessageStatus.FAILED
            message.error = str(exc)[:500]
            self._audit_message(principal, message)
            return self._finish(event, TimelineEventStatus.FAILED, str(exc))

        message.status = MessageStatus.SENT
        message.provider = result.provider
        message.provider_message_id = result.provider_message_id
        message.sent_at = now
        event.sent_at = now
        if step.requires_confirmation:
            session.add(
                CheckIn(
                    organization_id=event.organization_id,
                    appointment_id=appointment.id,
                    patient_id=patient.id,
                    timeline_event_id=event.id,
                    question=step.title,
                    sent_at=now,
                    expires_at=appointment.scheduled_at,
                )
            )
        self._audit_message(principal, message)
        return self._finish(event, TimelineEventStatus.SENT, None)

    def _finish(
        self, event: PatientTimelineEvent, status: TimelineEventStatus, error: str | None
    ) -> TimelineEventStatus:
        event.status = status
        event.last_error = error[:500] if error else None
        self._session.commit()
        return status

    def _audit_message(self, principal: SystemPrincipal, message: Message) -> None:
        self._session.flush()
        record_audit(
            self._session,
            principal=principal,
            action=AuditAction.CREATE,
            entity_type="message",
            entity_id=message.id,
            patient_id=message.patient_id,
            purpose="prep_reminder",
            details={"status": message.status.value},
        )


def dispatch_due_reminders(
    session_factory: Callable[[], Session],
    provider: MessagingProvider,
    translator: Translator,
    *,
    now: dt.datetime,
    batch_size: int,
) -> dict[str, int]:
    """One dispatcher run (called every minute by Celery beat)."""
    with session_factory() as session:
        stale = fail_stale_sends(session, now=now)
        claimed = claim_due_events(session, now=now, limit=batch_size)

    outcomes: dict[str, int] = {"claimed": len(claimed), "stale_failed": stale}
    for event_id in claimed:
        with session_factory() as session:
            try:
                status = ReminderSender(session, provider, translator).send(event_id, now=now)
            except Exception:
                session.rollback()
                logger.exception("dispatch.event_failed", event_id=str(event_id))
                continue
        key = status.value.lower() if status else "skipped_not_ours"
        outcomes[key] = outcomes.get(key, 0) + 1
    logger.info("dispatch.run", **outcomes)
    return outcomes
