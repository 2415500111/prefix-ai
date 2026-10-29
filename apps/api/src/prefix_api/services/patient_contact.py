"""Contact between the care team and a patient: logging a call, and sending a short message.

A logged call closes the appointment's open "call the patient" tasks. A staff message is shown
in the patient's portal (Updates); it is never sent by SMS from here. Both are written by a
person, never generated, and both are audited.
"""

import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from prefix_api.db.models import Appointment, Message, Patient, Task
from prefix_api.domain.enums import (
    AuditAction,
    MessageChannel,
    MessageDirection,
    MessageStatus,
    TaskStatus,
    TaskType,
)
from prefix_api.domain.errors import NotFoundError
from prefix_api.domain.permissions import Permission
from prefix_api.domain.principal import StaffPrincipal
from prefix_api.repositories import appointments as appointments_repo
from prefix_api.services.audit import record_audit

CARE_TEAM_PROVIDER = "care_team"
"""Marks a message written by staff, as opposed to a reminder sent by the dispatcher."""

_OPEN = (TaskStatus.OPEN, TaskStatus.IN_PROGRESS)


class PatientContactService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def log_call(
        self, principal: StaffPrincipal, appointment_id: uuid.UUID, *, now: dt.datetime
    ) -> Task:
        principal.require(Permission.TASK_COMPLETE)
        appointment = self._appointment(principal, appointment_id)
        open_calls = self._session.scalars(
            select(Task)
            .where(
                Task.appointment_id == appointment.id,
                Task.type == TaskType.CALL_PATIENT,
                Task.status.in_(_OPEN),
            )
            .with_for_update()
        ).all()
        for task in open_calls:
            task.status = TaskStatus.DONE
            task.completed_at = now
            self._audit(principal, AuditAction.UPDATE, "task", task.id, appointment, "DONE")

        call = Task(
            organization_id=principal.organization_id,
            type=TaskType.CALL_PATIENT,
            title="Call with the patient logged",
            status=TaskStatus.DONE,
            appointment_id=appointment.id,
            patient_id=appointment.patient_id,
            assignee_id=principal.user_id,
            completed_at=now,
        )
        self._session.add(call)
        self._session.flush()
        self._audit(principal, AuditAction.CREATE, "task", call.id, appointment, "DONE")
        return call

    def message_patient(
        self,
        principal: StaffPrincipal,
        appointment_id: uuid.UUID,
        body: str,
        *,
        now: dt.datetime,
    ) -> Message:
        principal.require(Permission.MESSAGE_SEND)
        appointment = self._appointment(principal, appointment_id)
        patient = self._session.get(Patient, appointment.patient_id)
        if patient is None:  # pragma: no cover - the foreign key prevents this
            raise NotFoundError("Appointment not found")
        message = Message(
            organization_id=principal.organization_id,
            patient_id=patient.id,
            appointment_id=appointment.id,
            channel=MessageChannel.PORTAL,
            direction=MessageDirection.OUTBOUND,
            status=MessageStatus.DELIVERED,
            language=patient.preferred_language,
            body=body,
            provider=CARE_TEAM_PROVIDER,
            sent_at=now,
        )
        self._session.add(message)
        self._session.flush()
        self._audit(principal, AuditAction.CREATE, "message", message.id, appointment, None)
        return message

    def _appointment(self, principal: StaffPrincipal, appointment_id: uuid.UUID) -> Appointment:
        appointment = appointments_repo.get_appointment(
            self._session, principal.organization_id, appointment_id, for_update=True
        )
        if appointment is None:
            raise NotFoundError("Appointment not found")
        return appointment

    def _audit(
        self,
        principal: StaffPrincipal,
        action: AuditAction,
        entity_type: str,
        entity_id: uuid.UUID,
        appointment: Appointment,
        status: str | None,
    ) -> None:
        record_audit(
            self._session,
            principal=principal,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            patient_id=appointment.patient_id,
            purpose="care_team_contact",
            details={"status": status} if status else None,
        )
