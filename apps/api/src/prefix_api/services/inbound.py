"""Inbound patient replies (SMS/WhatsApp): link them to check-ins and act on them.

Free text that is not a clear YES/NO/HELP is never interpreted here; it is stored and put in
front of a person (a nurse review task). It could describe a red-flag symptom (safety rule b).
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
    Escalation,
    Message,
    Patient,
    PatientTimelineEvent,
    PrepStep,
    Task,
)
from prefix_api.domain.enums import (
    AppointmentStatus,
    AuditAction,
    CheckInResponse,
    CheckInStatus,
    EscalationSeverity,
    EscalationSource,
    MessageChannel,
    MessageDirection,
    MessageStatus,
    TaskType,
    TimelineEventStatus,
)
from prefix_api.domain.principal import SystemPrincipal
from prefix_api.domain.replies import parse_reply
from prefix_api.services.audit import record_audit

JOB = "inbound_messages"
TASK_DUE = dt.timedelta(hours=2)


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
        purpose="patient_reply",
        details={"status": response.value},
    )

    if check_in is None or response is CheckInResponse.OTHER:
        _task(
            session,
            patient,
            check_in.appointment_id if check_in else None,
            TaskType.NURSE_REVIEW,
            "Read a message from the patient",
            now,
        )
        return InboundResult(matched_patient=True, response=response, check_in_id=None)

    check_in.status = CheckInStatus.ANSWERED
    check_in.response = response
    check_in.answered_at = now
    event = (
        session.get(PatientTimelineEvent, check_in.timeline_event_id)
        if check_in.timeline_event_id
        else None
    )
    step = session.get(PrepStep, event.step_id) if event else None
    appointment = session.get(Appointment, check_in.appointment_id)

    if response is CheckInResponse.YES and event is not None:
        event.status = TimelineEventStatus.CONFIRMED
        event.confirmed_at = now
    elif response is CheckInResponse.NO:
        if step is not None and step.is_critical and appointment is not None:
            _escalate(
                session,
                patient,
                appointment,
                EscalationSeverity.HIGH,
                f"Patient replied NO to a critical prep step: {step.title}",
                now,
            )
            if appointment.status is not AppointmentStatus.CANCELLED:
                appointment.status = AppointmentStatus.AT_RISK
        _task(
            session,
            patient,
            check_in.appointment_id,
            TaskType.CALL_PATIENT,
            f"Patient cannot complete: {step.title if step else check_in.question}",
            now,
        )
    elif response is CheckInResponse.HELP and appointment is not None:
        _escalate(
            session,
            patient,
            appointment,
            EscalationSeverity.NORMAL,
            "Patient asked for help by message",
            now,
        )
        _task(
            session, patient, appointment.id, TaskType.NURSE_REVIEW, "Patient asked for help", now
        )

    record_audit(
        session,
        principal=principal,
        action=AuditAction.UPDATE,
        entity_type="check_in",
        entity_id=check_in.id,
        patient_id=patient.id,
        purpose="patient_reply",
        details={"status": response.value},
    )
    return InboundResult(matched_patient=True, response=response, check_in_id=check_in.id)


def _escalate(
    session: Session,
    patient: Patient,
    appointment: Appointment,
    severity: EscalationSeverity,
    summary: str,
    now: dt.datetime,
) -> None:
    escalation = Escalation(
        organization_id=patient.organization_id,
        patient_id=patient.id,
        appointment_id=appointment.id,
        source=EscalationSource.PATIENT_REPORTED_PROBLEM,
        severity=severity,
        summary=summary,
    )
    session.add(escalation)
    session.flush()
    record_audit(
        session,
        principal=SystemPrincipal(organization_id=patient.organization_id, job=JOB),
        action=AuditAction.CREATE,
        entity_type="escalation",
        entity_id=escalation.id,
        patient_id=patient.id,
        purpose="patient_reply",
    )


def _task(
    session: Session,
    patient: Patient,
    appointment_id: uuid.UUID | None,
    task_type: TaskType,
    title: str,
    now: dt.datetime,
) -> None:
    session.add(
        Task(
            organization_id=patient.organization_id,
            type=task_type,
            title=title[:300],
            appointment_id=appointment_id,
            patient_id=patient.id,
            due_at=now + TASK_DUE,
        )
    )
