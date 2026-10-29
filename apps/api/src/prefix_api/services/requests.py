"""Reschedule requests from patients, and the care team's answer.

A request is a RESCHEDULE task, as before: open is pending, done is approved, cancelled is
declined. Approving moves the procedure to the new time with the usual reschedule (which
rebuilds the prep timeline), keeping the same gap between arrival and start.
"""

import datetime as dt
import uuid
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from prefix_api.db.models import Appointment, Patient, ProcedureType, Task
from prefix_api.domain.enums import AuditAction, TaskStatus, TaskType
from prefix_api.domain.errors import ConflictError, NotFoundError
from prefix_api.domain.permissions import Permission
from prefix_api.domain.principal import StaffPrincipal
from prefix_api.schemas.appointments import AppointmentReschedule
from prefix_api.services.appointments import AppointmentService
from prefix_api.services.audit import record_audit

PURPOSE = "reschedule_request"
RECENT = dt.timedelta(days=7)
_OPEN = (TaskStatus.OPEN, TaskStatus.IN_PROGRESS)

RequestStatus = Literal["pending", "approved", "declined"]


def request_status(task: Task) -> RequestStatus:
    if task.status in _OPEN:
        return "pending"
    return "approved" if task.status is TaskStatus.DONE else "declined"


@dataclass(frozen=True, slots=True)
class RequestItem:
    task: Task
    appointment: Appointment
    patient_name: str
    procedure_name: str

    @property
    def status(self) -> RequestStatus:
        return request_status(self.task)


class RequestService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def overview(self, principal: StaffPrincipal, *, now: dt.datetime) -> list[RequestItem]:
        """Pending requests first (oldest first), then those answered in the last seven days."""
        principal.require(Permission.TASK_MANAGE)
        rows = self._session.execute(
            select(Task, Appointment, Patient, ProcedureType.name)
            .join(Appointment, Appointment.id == Task.appointment_id)
            .join(Patient, Patient.id == Task.patient_id)
            .join(ProcedureType, ProcedureType.id == Appointment.procedure_type_id)
            .where(
                Task.organization_id == principal.organization_id,
                Task.type == TaskType.RESCHEDULE,
            )
            .order_by(Task.created_at)
        ).all()
        items = [
            RequestItem(
                task=task,
                appointment=appointment,
                patient_name=f"{patient.first_name} {patient.last_name}",
                procedure_name=procedure_name,
            )
            for task, appointment, patient, procedure_name in rows
            if task.status in _OPEN
            or (task.completed_at is not None and task.completed_at > now - RECENT)
        ]
        items.sort(key=lambda item: (item.status != "pending", item.task.created_at))
        for item in items:
            self._audit(principal, AuditAction.LIST, item.task, None)
        return items

    def approve(
        self,
        principal: StaffPrincipal,
        task_id: uuid.UUID,
        scheduled_at: dt.datetime,
        *,
        now: dt.datetime,
    ) -> Task:
        principal.require(Permission.APPOINTMENT_WRITE)
        task = self._pending(principal, task_id)
        appointment = self._session.get(Appointment, task.appointment_id)
        if appointment is None:  # pragma: no cover - the foreign key prevents this
            raise NotFoundError("Request not found")
        arrival_at = None
        if appointment.arrival_at is not None:
            arrival_at = scheduled_at - (appointment.scheduled_at - appointment.arrival_at)
        AppointmentService(self._session).reschedule(
            principal,
            appointment.id,
            AppointmentReschedule(scheduled_at=scheduled_at, arrival_at=arrival_at),
            now=now,
        )
        task.status = TaskStatus.DONE
        task.completed_at = now
        self._audit(principal, AuditAction.UPDATE, task, "approved")
        return task

    def decline(self, principal: StaffPrincipal, task_id: uuid.UUID, *, now: dt.datetime) -> Task:
        principal.require(Permission.APPOINTMENT_WRITE)
        task = self._pending(principal, task_id)
        task.status = TaskStatus.CANCELLED
        task.completed_at = now
        self._audit(principal, AuditAction.UPDATE, task, "declined")
        return task

    def _pending(self, principal: StaffPrincipal, task_id: uuid.UUID) -> Task:
        task = self._session.scalar(
            select(Task)
            .where(
                Task.id == task_id,
                Task.organization_id == principal.organization_id,
                Task.type == TaskType.RESCHEDULE,
            )
            .with_for_update()
        )
        if task is None or task.appointment_id is None:
            raise NotFoundError("Request not found")
        if task.status not in _OPEN:
            raise ConflictError(f"This request was already {request_status(task)}")
        return task

    def _audit(
        self, principal: StaffPrincipal, action: AuditAction, task: Task, status: str | None
    ) -> None:
        record_audit(
            self._session,
            principal=principal,
            action=action,
            entity_type="task",
            entity_id=task.id,
            patient_id=task.patient_id,
            purpose=PURPOSE,
            details={"status": status} if status else None,
        )
