"""Appointments, and the prep timeline that follows them. Every change is audited."""

import datetime as dt
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from prefix_api.db.models import (
    Appointment,
    CheckIn,
    Patient,
    PatientTimelineEvent,
    PrepProtocol,
    PrepStep,
    User,
)
from prefix_api.domain.enums import (
    AppointmentStatus,
    AuditAction,
    CheckInResponse,
    CheckInStatus,
    ProtocolStatus,
    Role,
    TimelineEventStatus,
)
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
from prefix_api.services.check_ins import record_answer
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

    def confirm_step(
        self,
        principal: StaffPrincipal,
        appointment_id: uuid.UUID,
        event_id: uuid.UUID,
        *,
        now: dt.datetime,
    ) -> PatientTimelineEvent:
        """Record that a step was done, on the patient's behalf (for example after a phone call)."""
        principal.require(Permission.STEP_CONFIRM)
        appointment = self._load(principal, appointment_id, for_update=True)
        event = self._session.scalar(
            select(PatientTimelineEvent)
            .where(
                PatientTimelineEvent.id == event_id,
                PatientTimelineEvent.appointment_id == appointment.id,
                PatientTimelineEvent.organization_id == principal.organization_id,
            )
            .with_for_update()
        )
        if event is None or event.status is TimelineEventStatus.CANCELLED:
            raise NotFoundError("Step not found")
        step = self._session.get(PrepStep, event.step_id)
        patient = self._session.get(Patient, appointment.patient_id)
        if step is None or patient is None:  # pragma: no cover - foreign keys prevent this
            raise NotFoundError("Step not found")
        if not step.requires_confirmation:
            raise ValidationFailedError("This step has nothing to confirm")
        if event.status is TimelineEventStatus.CONFIRMED:
            raise ConflictError("This step is already confirmed")

        check_in = self._session.scalar(
            select(CheckIn).where(CheckIn.timeline_event_id == event.id)
        )
        if check_in is None:
            check_in = CheckIn(
                organization_id=event.organization_id,
                appointment_id=event.appointment_id,
                patient_id=event.patient_id,
                timeline_event_id=event.id,
                question=step.title,
                status=CheckInStatus.PENDING,
            )
            self._session.add(check_in)
            self._session.flush()
        record_answer(
            self._session,
            principal=principal,
            patient=patient,
            appointment=appointment,
            check_in=check_in,
            event=event,
            step=step,
            response=CheckInResponse.YES,
            via="by staff",
            purpose="staff_step_confirmation",
            now=now,
        )
        return event

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
