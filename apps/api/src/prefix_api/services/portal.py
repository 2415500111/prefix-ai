"""The patient's own view of their procedures, and what they can do from the portal.

Every query is scoped to the signed-in patient (not just the organization): a patient can
never see or act on another patient's appointment, even within the same hospital.
"""

import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from prefix_api.db.models import (
    Appointment,
    CheckIn,
    Facility,
    Message,
    Patient,
    PatientTimelineEvent,
    PrepStep,
    ProcedureType,
    Task,
)
from prefix_api.domain.enums import (
    AppointmentStatus,
    AuditAction,
    CheckInResponse,
    CheckInStatus,
    MessageChannel,
    MessageDirection,
    MessageStatus,
    TaskStatus,
    TaskType,
    TimelineEventStatus,
)
from prefix_api.domain.errors import AuthenticationError, ConflictError, NotFoundError
from prefix_api.domain.portal import StepView, step_view
from prefix_api.domain.principal import PatientPrincipal
from prefix_api.schemas.portal import PortalAppointment, PortalFacility, PortalStep
from prefix_api.services.audit import record_audit
from prefix_api.services.check_ins import create_task, record_answer

PURPOSE_VIEW = "patient_self_access"
PURPOSE_ACTION = "patient_portal_check_in"
VIA = "in the patient portal"
# Show today's procedure until the end of its day, even after its start time.
SHOW_PAST_FOR = dt.timedelta(hours=12)
MAX_APPOINTMENTS = 5
_CLOSED = frozenset({AppointmentStatus.CANCELLED, AppointmentStatus.COMPLETED})
_OPEN_TASK = (TaskStatus.OPEN, TaskStatus.IN_PROGRESS)


class PortalService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_appointments(
        self, principal: PatientPrincipal, *, now: dt.datetime
    ) -> list[PortalAppointment]:
        rows = self._session.execute(
            select(Appointment, ProcedureType, Facility)
            .join(ProcedureType, ProcedureType.id == Appointment.procedure_type_id)
            .join(Facility, Facility.id == Appointment.facility_id)
            .where(
                Appointment.organization_id == principal.organization_id,
                Appointment.patient_id == principal.patient_id,
                Appointment.status.not_in(_CLOSED),
                Appointment.scheduled_at >= now - SHOW_PAST_FOR,
            )
            .order_by(Appointment.scheduled_at)
            .limit(MAX_APPOINTMENTS)
        ).all()
        result = []
        for appointment, procedure, facility in rows:
            record_audit(
                self._session,
                principal=principal,
                action=AuditAction.READ,
                entity_type="appointment",
                entity_id=appointment.id,
                patient_id=principal.patient_id,
                purpose=PURPOSE_VIEW,
            )
            result.append(self._present(appointment, procedure, facility, now))
        return result

    def confirm_step(
        self, principal: PatientPrincipal, event_id: uuid.UUID, *, now: dt.datetime
    ) -> None:
        patient, appointment, event, step, view = self._load_step(principal, event_id, now)
        if not view.can_confirm:
            raise ConflictError("This step cannot be confirmed yet")
        record_answer(
            self._session,
            principal=principal,
            patient=patient,
            appointment=appointment,
            check_in=self._check_in_for(event, step, now),
            event=event,
            step=step,
            response=CheckInResponse.YES,
            via=VIA,
            purpose=PURPOSE_ACTION,
            now=now,
        )

    def report_problem(
        self,
        principal: PatientPrincipal,
        event_id: uuid.UUID,
        *,
        note: str | None,
        now: dt.datetime,
    ) -> None:
        patient, appointment, event, step, view = self._load_step(principal, event_id, now)
        if not view.can_report_problem:
            raise ConflictError("A problem has already been reported for this step")
        record_answer(
            self._session,
            principal=principal,
            patient=patient,
            appointment=appointment,
            check_in=self._check_in_for(event, step, now),
            event=event,
            step=step,
            response=CheckInResponse.NO,
            via=VIA,
            purpose=PURPOSE_ACTION,
            now=now,
            note=note or None,
        )

    def request_reschedule(
        self,
        principal: PatientPrincipal,
        appointment_id: uuid.UUID,
        *,
        note: str | None,
        now: dt.datetime,
    ) -> None:
        appointment = self._load_appointment(principal, appointment_id, for_update=True)
        if self._reschedule_requested(appointment.id):
            return  # Asking twice is harmless; the coordinators already have a task.
        patient = self._patient(principal)
        task = create_task(
            self._session,
            patient=patient,
            appointment_id=appointment.id,
            task_type=TaskType.RESCHEDULE,
            title="Patient asked to reschedule",
            now=now,
        )
        self._session.flush()
        record_audit(
            self._session,
            principal=principal,
            action=AuditAction.CREATE,
            entity_type="task",
            entity_id=task.id,
            patient_id=patient.id,
            purpose="patient_reschedule_request",
        )
        if note:
            # Free text may contain PHI: it is kept as an (encrypted) message from the
            # patient, never in the task title.
            message = Message(
                organization_id=patient.organization_id,
                patient_id=patient.id,
                appointment_id=appointment.id,
                channel=MessageChannel.PORTAL,
                direction=MessageDirection.INBOUND,
                status=MessageStatus.RECEIVED,
                language=patient.preferred_language,
                body=note,
                sent_at=now,
            )
            self._session.add(message)
            self._session.flush()
            record_audit(
                self._session,
                principal=principal,
                action=AuditAction.CREATE,
                entity_type="message",
                entity_id=message.id,
                patient_id=patient.id,
                purpose="patient_reschedule_request",
            )

    # -- helpers -------------------------------------------------------------------------

    def _present(
        self,
        appointment: Appointment,
        procedure: ProcedureType,
        facility: Facility,
        now: dt.datetime,
    ) -> PortalAppointment:
        rows = self._session.execute(
            select(PatientTimelineEvent, PrepStep, CheckIn.response)
            .join(PrepStep, PrepStep.id == PatientTimelineEvent.step_id)
            .outerjoin(CheckIn, CheckIn.timeline_event_id == PatientTimelineEvent.id)
            .where(
                PatientTimelineEvent.appointment_id == appointment.id,
                PatientTimelineEvent.status != TimelineEventStatus.CANCELLED,
            )
            .order_by(PatientTimelineEvent.due_at, PrepStep.sort_order)
        ).all()
        steps = []
        for event, step, response in rows:
            view = _view(event, step, response, now)
            steps.append(
                PortalStep(
                    event_id=event.id,
                    title=step.title,
                    instruction=step.instruction_text,
                    category=step.category,
                    is_critical=step.is_critical,
                    requires_confirmation=step.requires_confirmation,
                    due_at=event.due_at,
                    state=view.state,
                    can_confirm=view.can_confirm,
                    can_report_problem=view.can_report_problem,
                )
            )
        return PortalAppointment(
            id=appointment.id,
            procedure_name=procedure.name,
            scheduled_at=appointment.scheduled_at,
            arrival_at=appointment.arrival_at,
            duration_minutes=appointment.duration_minutes,
            status=appointment.status,
            facility=PortalFacility(
                name=facility.name,
                address=facility.address,
                maps_url=facility.maps_url,
                phone=facility.phone,
                timezone=facility.timezone,
            ),
            steps=steps,
            reschedule_requested=self._reschedule_requested(appointment.id),
        )

    def _reschedule_requested(self, appointment_id: uuid.UUID) -> bool:
        return (
            self._session.scalar(
                select(Task.id)
                .where(
                    Task.appointment_id == appointment_id,
                    Task.type == TaskType.RESCHEDULE,
                    Task.status.in_(_OPEN_TASK),
                )
                .limit(1)
            )
            is not None
        )

    def _patient(self, principal: PatientPrincipal) -> Patient:
        patient = self._session.get(Patient, principal.patient_id)
        if patient is None or patient.organization_id != principal.organization_id:
            raise AuthenticationError("Patient session is no longer valid")
        return patient

    def _load_appointment(
        self, principal: PatientPrincipal, appointment_id: uuid.UUID, *, for_update: bool = False
    ) -> Appointment:
        query = select(Appointment).where(
            Appointment.id == appointment_id,
            Appointment.organization_id == principal.organization_id,
            Appointment.patient_id == principal.patient_id,
        )
        if for_update:
            query = query.with_for_update()
        appointment = self._session.scalar(query)
        if appointment is None:
            raise NotFoundError("Appointment not found")
        if appointment.status in _CLOSED:
            raise ConflictError(f"This appointment is {appointment.status.value.lower()}")
        return appointment

    def _load_step(
        self, principal: PatientPrincipal, event_id: uuid.UUID, now: dt.datetime
    ) -> tuple[Patient, Appointment, PatientTimelineEvent, PrepStep, StepView]:
        event = self._session.scalar(
            select(PatientTimelineEvent)
            .where(
                PatientTimelineEvent.id == event_id,
                PatientTimelineEvent.organization_id == principal.organization_id,
                PatientTimelineEvent.patient_id == principal.patient_id,
                PatientTimelineEvent.status != TimelineEventStatus.CANCELLED,
            )
            .with_for_update()
        )
        if event is None:
            raise NotFoundError("Step not found")
        appointment = self._load_appointment(principal, event.appointment_id, for_update=True)
        step = self._session.get_one(PrepStep, event.step_id)
        check_in = self._existing_check_in(event.id)
        view = _view(event, step, check_in.response if check_in else None, now)
        return self._patient(principal), appointment, event, step, view

    def _existing_check_in(self, event_id: uuid.UUID) -> CheckIn | None:
        return self._session.scalar(
            select(CheckIn).where(CheckIn.timeline_event_id == event_id).with_for_update()
        )

    def _check_in_for(
        self, event: PatientTimelineEvent, step: PrepStep, now: dt.datetime
    ) -> CheckIn:
        """The step's check-in: the one its reminder opened, or a new one for portal answers."""
        check_in = self._existing_check_in(event.id)
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
        return check_in


def _view(
    event: PatientTimelineEvent,
    step: PrepStep,
    response: CheckInResponse | None,
    now: dt.datetime,
) -> StepView:
    return step_view(
        status=event.status,
        requires_confirmation=step.requires_confirmation,
        send_at=event.send_at,
        due_at=event.due_at,
        last_response=response,
        now=now,
    )
