"""Inbound patient replies (SMS/WhatsApp): link them to check-ins and act on them.

Free text that is not a clear YES/NO/HELP is never interpreted here; it is stored and put in
front of a person (a nurse review task and a staff notification). It could describe a red-flag
symptom (safety rule b): the deterministic red-flag check marks that notification urgent.
"""

import datetime as dt
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from prefix_api.core.crypto import get_blind_indexer, normalize_phone
from prefix_api.db.models import (
    Appointment,
    CheckIn,
    Message,
    Patient,
    PatientTimelineEvent,
    PrepStep,
)
from prefix_api.domain.enums import (
    AuditAction,
    CheckInResponse,
    CheckInStatus,
    MessageChannel,
    MessageDirection,
    MessageStatus,
    StaffNotificationKind,
    TaskType,
)
from prefix_api.domain.principal import SystemPrincipal
from prefix_api.domain.red_flags import describe, detect_red_flags
from prefix_api.domain.replies import parse_reply
from prefix_api.services.audit import record_audit
from prefix_api.services.check_ins import create_task, record_answer
from prefix_api.services.staff_notifications import notify_staff

JOB = "inbound_messages"
PURPOSE = "patient_reply"


@dataclass(frozen=True, slots=True)
class InboundResult:
    matched_patient: bool
    response: CheckInResponse | None
    check_in_id: uuid.UUID | None


def _latest_open_check_in(session: Session, patient_ids: list[uuid.UUID]) -> CheckIn | None:
    """The question a reply most likely answers: the most recently sent one; when several
    went out together, the one due last (closest to the procedure)."""
    return session.scalar(
        select(CheckIn)
        .outerjoin(PatientTimelineEvent, PatientTimelineEvent.id == CheckIn.timeline_event_id)
        .where(CheckIn.patient_id.in_(patient_ids), CheckIn.status == CheckInStatus.PENDING)
        .order_by(
            CheckIn.sent_at.desc().nulls_last(),
            PatientTimelineEvent.due_at.desc().nulls_last(),
            CheckIn.created_at.desc(),
        )
        .limit(1)
        .with_for_update(of=CheckIn)
    )


def handle_inbound_message(
    session: Session,
    *,
    from_phone: str,
    body: str,
    channel: MessageChannel,
    provider: str,
    provider_message_id: str | None,
    now: dt.datetime,
) -> InboundResult:
    bidx = get_blind_indexer().index(normalize_phone(from_phone), "phone")
    patients = list(session.scalars(select(Patient).where(Patient.phone_bidx == bidx)))
    if not patients:
        return InboundResult(matched_patient=False, response=None, check_in_id=None)

    check_in = _latest_open_check_in(session, [p.id for p in patients])
    patient = next((p for p in patients if check_in and p.id == check_in.patient_id), patients[0])
    principal = SystemPrincipal(organization_id=patient.organization_id, job=JOB)
    response = parse_reply(body)

    message = Message(
        organization_id=patient.organization_id,
        patient_id=patient.id,
        appointment_id=check_in.appointment_id if check_in else None,
        channel=channel,
        direction=MessageDirection.INBOUND,
        status=MessageStatus.RECEIVED,
        language=patient.preferred_language,
        body=body[:2000],
        provider=provider,
        provider_message_id=provider_message_id,
        sent_at=now,
    )
    session.add(message)
    session.flush()
    record_audit(
        session,
        principal=principal,
        action=AuditAction.CREATE,
        entity_type="message",
        entity_id=message.id,
        patient_id=patient.id,
        purpose=PURPOSE,
        details={"status": response.value},
    )

    if check_in is None or response is CheckInResponse.OTHER:
        task = create_task(
            session,
            patient=patient,
            appointment_id=check_in.appointment_id if check_in else None,
            task_type=TaskType.NURSE_REVIEW,
            title="Read a message from the patient",
            now=now,
        )
        flags = detect_red_flags(body)
        notify_staff(
            session,
            principal=principal,
            patient=patient,
            appointment_id=check_in.appointment_id if check_in else None,
            kind=StaffNotificationKind.MESSAGE,
            summary="Sent a message" + (f". Mentions {describe(flags)}" if flags else ""),
            now=now,
            red_flag=bool(flags),
            task=task,
        )
        return InboundResult(matched_patient=True, response=response, check_in_id=None)

    event = (
        session.get(PatientTimelineEvent, check_in.timeline_event_id)
        if check_in.timeline_event_id
        else None
    )
    record_answer(
        session,
        principal=principal,
        patient=patient,
        appointment=session.get(Appointment, check_in.appointment_id),
        check_in=check_in,
        event=event,
        step=session.get(PrepStep, event.step_id) if event else None,
        response=response,
        via="by message",
        purpose=PURPOSE,
        now=now,
    )
    return InboundResult(matched_patient=True, response=response, check_in_id=check_in.id)
