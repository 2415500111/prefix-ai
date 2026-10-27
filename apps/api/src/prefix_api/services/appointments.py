"""Appointments, and the prep timeline that follows them. Every change is audited."""

import datetime as dt
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from prefix_api.db.models import (
    Appointment,
    PatientTimelineEvent,
    PrepProtocol,
    PrepStep,
    User,
)
from prefix_api.domain.enums import AppointmentStatus, AuditAction, ProtocolStatus, Role
from prefix_api.domain.errors import ConflictError, NotFoundError, ValidationFailedError
from prefix_api.domain.permissions import Permission
from prefix_api.domain.principal import StaffPrincipal
from prefix_api.repositories import appointments as appointments_repo
from prefix_api.repositories import organizations as org_repo
from prefix_api.repositories import patients as patients_repo
from prefix_api.repositories import protocols as protocols_repo
from prefix_api.schemas.appointments import (
    AppointmentCancel,
    AppointmentCreate,
    AppointmentReschedule,
)
from prefix_api.services.audit import record_audit
from prefix_api.services.timeline import build_timeline, cancel_events

ENTITY = "appointment"
_CLOSED = frozenset({AppointmentStatus.CANCELLED, AppointmentStatus.COMPLETED})


@dataclass(frozen=True, slots=True)
class TimelineEntry:
    event: PatientTimelineEvent
    step: PrepStep


class AppointmentService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self, principal: StaffPrincipal, data: AppointmentCreate, *, now: dt.datetime
    ) -> Appointment:
        principal.require(Permission.APPOINTMENT_WRITE)
        org_id = principal.organization_id
        if data.scheduled_at <= now:
            raise ValidationFailedError("The procedure must be scheduled in the future")
        if patients_repo.get_patient(self._session, org_id, data.patient_id) is None:
            raise ValidationFailedError("Unknown patient")
        if org_repo.get_facility(self._session, org_id, data.facility_id) is None:
            raise ValidationFailedError("Unknown facility")
        procedure_type = org_repo.get_procedure_type(self._session, org_id, data.procedure_type_id)
        if procedure_type is None:
            raise ValidationFailedError("Unknown procedure type")
        if data.clinician_id is not None:
            clinician = self._session.get(User, data.clinician_id)
            if clinician is None or clinician.organization_id != org_id:
                raise ValidationFailedError("Unknown clinician")
            if clinician.role is not Role.CLINICIAN:
                raise ValidationFailedError("The assigned clinician must have the CLINICIAN role")

        appointment = Appointment(
            organization_id=org_id,
            patient_id=data.patient_id,
            facility_id=data.facility_id,
            procedure_type_id=data.procedure_type_id,
            clinician_id=data.clinician_id,
            protocol_id=self._choose_protocol(principal, data).id,
            scheduled_at=data.scheduled_at,
            arrival_at=data.arrival_at,
            duration_minutes=data.duration_minutes or procedure_type.default_duration_minutes,
            status=AppointmentStatus.SCHEDULED,
        )
        self._session.add(appointment)
        self._session.flush()
        build_timeline(self._session, appointment, now=now)
        self._audit(principal, AuditAction.CREATE, appointment, purpose="appointment_booking")
        return appointment

    def reschedule(
        self,
        principal: StaffPrincipal,
        appointment_id: uuid.UUID,
        data: AppointmentReschedule,
        *,
        now: dt.datetime,
    ) -> Appointment:
        principal.require(Permission.APPOINTMENT_WRITE)
        appointment = self._load(principal, appointment_id, for_update=True)
        if appointment.status in _CLOSED:
            raise ConflictError(f"A {appointment.status.value.lower()} appointment cannot move")
        if data.scheduled_at <= now:
            raise ValidationFailedError("The procedure must be scheduled in the future")
        appointment.scheduled_at = data.scheduled_at
        appointment.arrival_at = data.arrival_at
        appointment.status = AppointmentStatus.SCHEDULED
        build_timeline(self._session, appointment, now=now)
        self._audit(
            principal,
            AuditAction.UPDATE,
            appointment,
            purpose="appointment_reschedule",
            details={"fields": ["scheduled_at", "arrival_at"]},
        )
        return appointment

    def cancel(
        self,
        principal: StaffPrincipal,
        appointment_id: uuid.UUID,
        data: AppointmentCancel,
        *,
        now: dt.datetime,
    ) -> Appointment:
        principal.require(Permission.APPOINTMENT_WRITE)
        appointment = self._load(principal, appointment_id, for_update=True)
        if appointment.status in _CLOSED:
            raise ConflictError(f"The appointment is already {appointment.status.value.lower()}")
        appointment.status = AppointmentStatus.CANCELLED
        appointment.cancellation_reason = data.reason
        appointment.cancellation_note = data.note
        appointment.cancelled_at = now
        cancel_events(self._session, appointment)
        self._audit(
            principal,
            AuditAction.UPDATE,
            appointment,
            purpose="appointment_cancellation",
            details={"status": "CANCELLED", "reason": data.reason.value},
        )
        return appointment

    def get(
        self, principal: StaffPrincipal, appointment_id: uuid.UUID
    ) -> tuple[Appointment, list[TimelineEntry]]:
        principal.require(Permission.APPOINTMENT_READ)
        appointment = self._load(principal, appointment_id)
        rows = self._session.execute(
            select(PatientTimelineEvent, PrepStep)
            .join(PrepStep, PrepStep.id == PatientTimelineEvent.step_id)
            .where(PatientTimelineEvent.appointment_id == appointment.id)
            .order_by(PatientTimelineEvent.due_at, PrepStep.sort_order)
        ).all()
        self._audit(principal, AuditAction.READ, appointment, purpose="appointment_view")
        return appointment, [TimelineEntry(event=e, step=s) for e, s in rows]

    def list_between(
        self, principal: StaffPrincipal, *, start: dt.datetime, end: dt.datetime, limit: int
    ) -> list[Appointment]:
        principal.require(Permission.APPOINTMENT_READ)
        appointments = appointments_repo.list_appointments(
            self._session, principal.organization_id, start=start, end=end, limit=limit
        )
        for appointment in appointments:
            self._audit(principal, AuditAction.LIST, appointment, purpose="appointment_list")
        return appointments

    def _choose_protocol(self, principal: StaffPrincipal, data: AppointmentCreate) -> PrepProtocol:
        if data.protocol_id is not None:
            protocol = protocols_repo.get_protocol(
                self._session, principal.organization_id, data.protocol_id
            )
            if protocol is None or protocol.procedure_type_id != data.procedure_type_id:
                raise ValidationFailedError("Unknown protocol for this procedure")
            if protocol.status is not ProtocolStatus.APPROVED:
                raise ValidationFailedError("Only an approved protocol can be used for patients")
            return protocol
        approved = protocols_repo.list_approved_for_procedure(
            self._session, principal.organization_id, data.procedure_type_id
        )
        if not approved:
            raise ValidationFailedError(
                "No approved protocol exists for this procedure; a clinician must approve one"
            )
        if len(approved) > 1:
            raise ValidationFailedError(
                "Several approved protocols exist for this procedure; choose one (protocol_id)"
            )
        return approved[0]

    def _load(
        self, principal: StaffPrincipal, appointment_id: uuid.UUID, *, for_update: bool = False
    ) -> Appointment:
        appointment = appointments_repo.get_appointment(
            self._session, principal.organization_id, appointment_id, for_update=for_update
        )
        if appointment is None:
            raise NotFoundError("Appointment not found")
        return appointment

    def _audit(
        self,
        principal: StaffPrincipal,
        action: AuditAction,
        appointment: Appointment,
        *,
        purpose: str,
        details: dict[str, object] | None = None,
    ) -> None:
        record_audit(
            self._session,
            principal=principal,
            action=action,
            entity_type=ENTITY,
            entity_id=appointment.id,
            patient_id=appointment.patient_id,
            purpose=purpose,
            details=details,
        )
