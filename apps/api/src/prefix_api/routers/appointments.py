import datetime as dt
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from prefix_api.api.deps import DbSession, Now, patient_data_route, require
from prefix_api.db.models import Appointment
from prefix_api.domain.permissions import Permission
from prefix_api.domain.principal import StaffPrincipal
from prefix_api.schemas.appointments import (
    AppointmentCancel,
    AppointmentCreate,
    AppointmentDetailOut,
    AppointmentOut,
    AppointmentReschedule,
    TimelineEventOut,
)
from prefix_api.services.appointments import AppointmentService, TimelineEntry

router = APIRouter(
    prefix="/appointments", tags=["appointments"], dependencies=[Depends(patient_data_route)]
)

Reader = Annotated[StaffPrincipal, Depends(require(Permission.APPOINTMENT_READ))]
Writer = Annotated[StaffPrincipal, Depends(require(Permission.APPOINTMENT_WRITE))]


def _detail(appointment: Appointment, timeline: list[TimelineEntry]) -> AppointmentDetailOut:
    base = AppointmentOut.model_validate(appointment)
    return AppointmentDetailOut(
        **base.model_dump(),
        timeline=[
            TimelineEventOut(
                id=entry.event.id,
                step_id=entry.step.id,
                title=entry.step.title,
                category=entry.step.category,
                is_critical=entry.step.is_critical,
                requires_confirmation=entry.step.requires_confirmation,
                due_at=entry.event.due_at,
                send_at=entry.event.send_at,
                status=entry.event.status,
                sent_at=entry.event.sent_at,
                confirmed_at=entry.event.confirmed_at,
            )
            for entry in timeline
        ],
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def create_appointment(
    body: AppointmentCreate, principal: Writer, session: DbSession, now: Now
) -> AppointmentOut:
    return AppointmentOut.model_validate(
        AppointmentService(session).create(principal, body, now=now)
    )


@router.get("")
def list_appointments(
    principal: Reader,
    session: DbSession,
    now: Now,
    days: Annotated[int, Query(ge=1, le=31)] = 3,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> list[AppointmentOut]:
    """Upcoming appointments in the next ``days`` days."""
    appointments = AppointmentService(session).list_between(
        principal, start=now, end=now + dt.timedelta(days=days), limit=limit
    )
    return [AppointmentOut.model_validate(a) for a in appointments]


@router.get("/{appointment_id}")
def get_appointment(
    appointment_id: uuid.UUID, principal: Reader, session: DbSession
) -> AppointmentDetailOut:
    appointment, timeline = AppointmentService(session).get(principal, appointment_id)
    return _detail(appointment, timeline)


@router.post("/{appointment_id}/reschedule")
def reschedule_appointment(
    appointment_id: uuid.UUID,
    body: AppointmentReschedule,
    principal: Writer,
    session: DbSession,
    now: Now,
) -> AppointmentOut:
    appointment = AppointmentService(session).reschedule(principal, appointment_id, body, now=now)
    return AppointmentOut.model_validate(appointment)


@router.post("/{appointment_id}/cancel")
def cancel_appointment(
    appointment_id: uuid.UUID,
    body: AppointmentCancel,
    principal: Writer,
    session: DbSession,
    now: Now,
) -> AppointmentOut:
    appointment = AppointmentService(session).cancel(principal, appointment_id, body, now=now)
    return AppointmentOut.model_validate(appointment)
