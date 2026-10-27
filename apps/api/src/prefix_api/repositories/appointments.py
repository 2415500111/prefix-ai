import datetime as dt
import uuid

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from prefix_api.db.models import Appointment, CheckIn, PatientTimelineEvent
from prefix_api.domain.enums import CheckInStatus, TimelineEventStatus


def get_appointment(
    session: Session,
    organization_id: uuid.UUID,
    appointment_id: uuid.UUID,
    *,
    for_update: bool = False,
) -> Appointment | None:
    query = select(Appointment).where(
        Appointment.id == appointment_id, Appointment.organization_id == organization_id
    )
    if for_update:
        query = query.with_for_update()
    return session.scalar(query)


def list_appointments(
    session: Session,
    organization_id: uuid.UUID,
    *,
    start: dt.datetime,
    end: dt.datetime,
    limit: int,
) -> list[Appointment]:
    return list(
        session.scalars(
            select(Appointment)
            .where(
                Appointment.organization_id == organization_id,
                Appointment.scheduled_at >= start,
                Appointment.scheduled_at < end,
            )
            .order_by(Appointment.scheduled_at)
            .limit(limit)
        )
    )


def active_events(session: Session, appointment_id: uuid.UUID) -> list[PatientTimelineEvent]:
    return list(
        session.scalars(
            select(PatientTimelineEvent)
            .where(
                PatientTimelineEvent.appointment_id == appointment_id,
                PatientTimelineEvent.status != TimelineEventStatus.CANCELLED,
            )
            .order_by(PatientTimelineEvent.due_at)
            .with_for_update()
        )
    )


def expire_pending_check_ins(session: Session, event_ids: list[uuid.UUID]) -> None:
    if not event_ids:
        return
    session.execute(
        update(CheckIn)
        .where(
            CheckIn.timeline_event_id.in_(event_ids),
            CheckIn.status == CheckInStatus.PENDING,
        )
        .values(status=CheckInStatus.EXPIRED)
    )
