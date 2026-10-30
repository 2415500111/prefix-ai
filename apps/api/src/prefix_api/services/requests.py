"""Reschedule requests from patients, and the care team's answer.

A request is a RESCHEDULE task, as before: open is pending, done is approved, cancelled is
declined. Approving moves the procedure to the new time with the usual reschedule (which
rebuilds the prep timeline), keeping the same gap between arrival and start.

The list is newest first by when the patient asked, ordered by the database.
"""

import datetime as dt
import uuid
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from prefix_api.db.models import (
    Appointment,
    Facility,
    Patient,
    ProcedureType,
    StaffNotification,
    Task,
)
from prefix_api.domain.enums import AuditAction, TaskStatus, TaskType
from prefix_api.domain.errors import ConflictError, NotFoundError
from prefix_api.domain.permissions import Permission
from prefix_api.domain.principal import StaffPrincipal
from prefix_api.domain.urgency import UrgentReason, urgent_reasons
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
    timezone: str
    urgent_reasons: tuple[UrgentReason, ...]

    @property
    def status(self) -> RequestStatus:
        return request_status(self.task)


class RequestService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def overview(self, principal: StaffPrincipal, *, now: dt.datetime) -> list[RequestItem]:
        """Open requests and those answered in the last seven days, newest first by when the
        patient asked (``created_at DESC, id DESC``, indexed). Urgency is shown, never sorted on.
        """
        principal.require(Permission.TASK_MANAGE)
        rows = self._session.execute(
            select(Task, Appointment, Patient, ProcedureType.name, Facility.timezone)
            .join(Appointment, Appointment.id == Task.appointment_id)
            .join(Patient, Patient.id == Task.patient_id)
            .join(ProcedureType, ProcedureType.id == Appointment.procedure_type_id)
            .join(Facility, Facility.id == Appointment.facility_id)
            .where(
                Task.organization_id == principal.organization_id,
                Task.type == TaskType.RESCHEDULE,
                or_(
                    Task.status.in_(_OPEN),
                    and_(Task.completed_at.is_not(None), Task.completed_at > now - RECENT),
                ),
            )
            .order_by(Task.created_at.desc(), Task.id.desc())
        ).all()
        flagged = self._red_flagged([row[0].id for row in rows])
        items = [
            RequestItem(
                task=task,
                appointment=appointment,
                patient_name=f"{patient.first_name} {patient.last_name}",
                procedure_name=procedure_name,
                timezone=timezone,
                urgent_reasons=urgent_reasons(
                    red_flag=task.id in flagged,
                    critical_step=False,
                    scheduled_at=appointment.scheduled_at,
                    now=now,
                ),
            )
            for task, appointment, patient, procedure_name, timezone in rows
        ]
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

    def _red_flagged(self, task_ids: list[uuid.UUID]) -> frozenset[uuid.UUID]:
        """Requests whose note had red-flag words (recorded on their notification)."""
        if not task_ids:
            return frozenset()
        flagged = self._session.scalars(
            select(StaffNotification.task_id).where(
                StaffNotification.task_id.in_(task_ids), StaffNotification.red_flag
            )
        )
        return frozenset(task_id for task_id in flagged if task_id is not None)

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
