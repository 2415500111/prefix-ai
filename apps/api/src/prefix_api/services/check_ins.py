"""Applying a patient's answer to a prep step, whichever way it arrived (SMS or portal).

YES confirms the step. NO creates a call task for the coordinators and, on a critical step,
a HIGH escalation and an AT_RISK appointment. HELP puts a nurse in front of the patient.
NO and HELP also appear in the staff notifications; red-flag words in the patient's note make
that item urgent.
"""

import datetime as dt
import uuid

from sqlalchemy.orm import Session

from prefix_api.db.models import (
    Appointment,
    CheckIn,
    Escalation,
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
    StaffNotificationKind,
    TaskType,
    TimelineEventStatus,
)
from prefix_api.domain.principal import Principal
from prefix_api.domain.red_flags import describe, detect_red_flags
from prefix_api.services.audit import record_audit
from prefix_api.services.staff_notifications import notify_staff

TASK_DUE = dt.timedelta(hours=2)


def record_answer(
    session: Session,
    *,
    principal: Principal,
    patient: Patient,
    appointment: Appointment | None,
    check_in: CheckIn,
    event: PatientTimelineEvent | None,
    step: PrepStep | None,
    response: CheckInResponse,
    via: str,
    purpose: str,
    now: dt.datetime,
    note: str | None = None,
) -> None:
    """Store the answer on ``check_in`` and act on it. ``via`` reads like "by message"."""
    check_in.status = CheckInStatus.ANSWERED
    check_in.response = response
    check_in.response_text = note
    check_in.answered_at = now
    label = step.title if step else check_in.question

    if response is CheckInResponse.YES and event is not None:
        event.status = TimelineEventStatus.CONFIRMED
        event.confirmed_at = now
    elif response is CheckInResponse.NO:
        escalation = None
        critical = step is not None and step.is_critical
        if critical and appointment is not None:
            escalation = create_escalation(
                session,
                principal=principal,
                patient=patient,
                appointment=appointment,
                severity=EscalationSeverity.HIGH,
                summary=_with_note(
                    f"Patient cannot complete a critical prep step ({via}): {label}", note
                ),
                purpose=purpose,
            )
            if appointment.status is not AppointmentStatus.CANCELLED:
                appointment.status = AppointmentStatus.AT_RISK
        task = create_task(
            session,
            patient=patient,
            appointment_id=check_in.appointment_id,
            task_type=TaskType.CALL_PATIENT,
            title=f"Patient cannot complete: {label}",
            now=now,
            escalation_id=escalation.id if escalation else None,
        )
        flags = detect_red_flags(note) if note else frozenset()
        notify_staff(
            session,
            principal=principal,
            patient=patient,
            appointment_id=check_in.appointment_id,
            kind=StaffNotificationKind.PROBLEM,
            summary=f"Cannot complete: {label}"
            + (f". Mentions {describe(flags)}" if flags else ""),
            now=now,
            red_flag=bool(flags),
            critical_step=critical,
            escalation=escalation,
            task=task,
        )
    elif response is CheckInResponse.HELP and appointment is not None:
        escalation = create_escalation(
            session,
            principal=principal,
            patient=patient,
            appointment=appointment,
            severity=EscalationSeverity.NORMAL,
            summary=_with_note(f"Patient asked for help ({via})", note),
            purpose=purpose,
        )
        task = create_task(
            session,
            patient=patient,
            appointment_id=appointment.id,
            task_type=TaskType.NURSE_REVIEW,
            title="Patient asked for help",
            now=now,
            escalation_id=escalation.id,
        )
        flags = detect_red_flags(note) if note else frozenset()
        notify_staff(
            session,
            principal=principal,
            patient=patient,
            appointment_id=appointment.id,
            kind=StaffNotificationKind.HELP,
            summary=f"Asked for help with: {label}"
            + (f". Mentions {describe(flags)}" if flags else ""),
            now=now,
            red_flag=bool(flags),
            escalation=escalation,
            task=task,
        )

    record_audit(
        session,
        principal=principal,
        action=AuditAction.UPDATE,
        entity_type="check_in",
        entity_id=check_in.id,
        patient_id=patient.id,
        purpose=purpose,
        details={"status": response.value},
    )


def _with_note(summary: str, note: str | None) -> str:
    # The escalation summary is encrypted, so the patient's own words may go there;
    # task titles are not encrypted and never include them.
    return f"{summary}\nPatient's note: {note}" if note else summary


def create_escalation(
    session: Session,
    *,
    principal: Principal,
    patient: Patient,
    appointment: Appointment,
    severity: EscalationSeverity,
    summary: str,
    purpose: str,
    source: EscalationSource = EscalationSource.PATIENT_REPORTED_PROBLEM,
) -> Escalation:
    escalation = Escalation(
        organization_id=patient.organization_id,
        patient_id=patient.id,
        appointment_id=appointment.id,
        source=source,
        severity=severity,
        summary=summary,
    )
    session.add(escalation)
    session.flush()
    record_audit(
        session,
        principal=principal,
        action=AuditAction.CREATE,
        entity_type="escalation",
        entity_id=escalation.id,
        patient_id=patient.id,
        purpose=purpose,
    )
    return escalation


def create_task(
    session: Session,
    *,
    patient: Patient,
    appointment_id: uuid.UUID | None,
    task_type: TaskType,
    title: str,
    now: dt.datetime,
    escalation_id: uuid.UUID | None = None,
    due_in: dt.timedelta = TASK_DUE,
) -> Task:
    task = Task(
        organization_id=patient.organization_id,
        type=task_type,
        title=title[:300],
        appointment_id=appointment_id,
        patient_id=patient.id,
        escalation_id=escalation_id,
        due_at=now + due_in,
    )
    session.add(task)
    return task
