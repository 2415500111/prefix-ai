"""Smart Prep Timeline: turns an appointment and its APPROVED protocol into scheduled events.

Only steps of an approved protocol can be scheduled (safety rule a); the database rejects
anything else (migration 0003). Rescheduling cancels the old events and creates new ones.
"""

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from prefix_api.db.models import (
    Appointment,
    Facility,
    Patient,
    PatientTimelineEvent,
    PrepProtocol,
)
from prefix_api.domain.conditions import patient_facts
from prefix_api.domain.enums import ProtocolStatus, TimelineEventStatus
from prefix_api.domain.errors import ConflictError
from prefix_api.domain.timeline import plan_step
from prefix_api.repositories import appointments as appointments_repo
from prefix_api.services.protocols import applicable_steps


def current_approved_version(session: Session, protocol: PrepProtocol) -> PrepProtocol | None:
    """The approved version in the protocol's family (protocols may be revised after booking)."""
    if protocol.status is ProtocolStatus.APPROVED:
        return protocol
    return session.scalar(
        select(PrepProtocol)
        .where(
            PrepProtocol.family_id == protocol.family_id,
            PrepProtocol.status == ProtocolStatus.APPROVED,
        )
        .options(selectinload(PrepProtocol.steps))
    )


def cancel_events(session: Session, appointment: Appointment) -> int:
    events = appointments_repo.active_events(session, appointment.id)
    for event in events:
        event.status = TimelineEventStatus.CANCELLED
    appointments_repo.expire_pending_check_ins(session, [e.id for e in events])
    session.flush()
    return len(events)


def build_timeline(
    session: Session, appointment: Appointment, *, now: dt.datetime
) -> list[PatientTimelineEvent]:
    """(Re)create the appointment's events from the current approved protocol version."""
    if appointment.protocol_id is None:
        raise ConflictError("The appointment has no protocol")
    booked = session.get(PrepProtocol, appointment.protocol_id)
    protocol = current_approved_version(session, booked) if booked else None
    if protocol is None:
        raise ConflictError("The appointment's protocol has no approved version")
    appointment.protocol_id = protocol.id

    patient = session.get(Patient, appointment.patient_id)
    facility = session.get(Facility, appointment.facility_id)
    if patient is None or facility is None:  # pragma: no cover - foreign keys guarantee these
        raise ConflictError("Appointment references missing records")

    cancel_events(session, appointment)
    events: list[PatientTimelineEvent] = []
    for step in applicable_steps(protocol, patient_facts(patient)):
        timing = plan_step(
            scheduled_at=appointment.scheduled_at,
            offset_minutes=step.offset_minutes,
            timezone=facility.timezone,
            is_critical=step.is_critical,
            now=now,
        )
        events.append(
            PatientTimelineEvent(
                organization_id=appointment.organization_id,
                appointment_id=appointment.id,
                patient_id=appointment.patient_id,
                step_id=step.id,
                due_at=timing.due_at,
                send_at=timing.send_at or timing.due_at,
                status=TimelineEventStatus.PENDING
                if timing.send_at is not None
                else TimelineEventStatus.SKIPPED,
            )
        )
    session.add_all(events)
    session.flush()
    return events
