"""Coordinator dashboard: the next procedures, one patient's drawer, and the task queue."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from prefix_api.api.deps import DbSession, Now, patient_data_route, require
from prefix_api.domain.permissions import Permission
from prefix_api.domain.principal import StaffPrincipal
from prefix_api.schemas.dashboard import (
    DrawerEscalationOut,
    DrawerMessageOut,
    DrawerOut,
    DrawerStepOut,
    DrawerTaskOut,
    QueueItemOut,
    ResendOut,
    UpcomingOut,
)
from prefix_api.services.dashboard import DashboardService, Drawer, UpcomingRow

router = APIRouter(
    prefix="/dashboard", tags=["dashboard"], dependencies=[Depends(patient_data_route)]
)

Reader = Annotated[StaffPrincipal, Depends(require(Permission.APPOINTMENT_READ))]
Writer = Annotated[StaffPrincipal, Depends(require(Permission.APPOINTMENT_WRITE))]
Queue = Annotated[StaffPrincipal, Depends(require(Permission.TASK_MANAGE))]


def _upcoming(row: UpcomingRow) -> UpcomingOut:
    appointment = row.appointment
    return UpcomingOut(
        appointment_id=appointment.id,
        patient_id=row.patient.id,
        patient_name=f"{row.patient.first_name} {row.patient.last_name}",
        procedure_name=row.procedure_name,
        facility_name=row.facility_name,
        scheduled_at=appointment.scheduled_at,
        status=appointment.status,
        readiness=row.readiness,
        required_steps=row.required_steps,
        confirmed_steps=row.confirmed_steps,
        problem_steps=row.problem_steps,
        open_escalations=row.open_escalations,
        open_tasks=row.open_tasks,
    )


def _drawer(drawer: Drawer) -> DrawerOut:
    return DrawerOut(
        appointment=_upcoming(drawer.row),
        steps=[
            DrawerStepOut(
                event_id=step.event.id,
                title=step.title,
                status=step.event.status,
                due_at=step.event.due_at,
                requires_confirmation=step.requires_confirmation,
                is_critical=step.is_critical,
                response=step.response,
            )
            for step in drawer.steps
        ],
        messages=[DrawerMessageOut.model_validate(message) for message in drawer.messages],
        escalations=[
            DrawerEscalationOut(
                id=e.id,
                severity=e.severity,
                status=e.status,
                summary=e.summary,
                created_at=e.created_at,
            )
            for e in drawer.escalations
        ],
        tasks=[
            DrawerTaskOut(id=t.id, type=t.type, title=t.title, status=t.status, due_at=t.due_at)
            for t in drawer.tasks
        ],
    )


@router.get("/upcoming")
def upcoming(
    principal: Reader,
    session: DbSession,
    now: Now,
    hours: Annotated[int, Query(ge=1, le=168)] = 72,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> list[UpcomingOut]:
    rows = DashboardService(session).upcoming(principal, now=now, hours=hours, limit=limit)
    return [_upcoming(row) for row in rows]


@router.get("/appointments/{appointment_id}")
def appointment_drawer(
    appointment_id: uuid.UUID, principal: Reader, session: DbSession, now: Now
) -> DrawerOut:
    return _drawer(DashboardService(session).drawer(principal, appointment_id, now=now))


@router.post("/appointments/{appointment_id}/resend-failed")
def resend_failed(
    appointment_id: uuid.UUID, principal: Writer, session: DbSession, now: Now
) -> ResendOut:
    count = DashboardService(session).resend_failed(principal, appointment_id, now=now)
    return ResendOut(queued=count)


@router.get("/queue")
def task_queue(principal: Queue, session: DbSession, now: Now) -> list[QueueItemOut]:
    items = DashboardService(session).queue(principal, now=now)
    return [
        QueueItemOut(
            id=item.task.id,
            type=item.task.type,
            title=item.task.title,
            status=item.task.status,
            patient_id=item.task.patient_id,
            patient_name=item.patient_name,
            appointment_id=item.task.appointment_id,
            due_at=item.task.due_at,
            sla=item.sla,
        )
        for item in items
    ]
