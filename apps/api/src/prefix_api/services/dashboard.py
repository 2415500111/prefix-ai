"""The coordinator dashboard: the next procedures, how ready each patient is, and the work queue.

Until the cancellation risk score exists (Phase 7), the order is: open escalations first, then
the least ready patient, then the soonest procedure. Every patient read is audit-logged.
"""

import datetime as dt
import uuid
from collections import Counter
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from prefix_api.db.models import (
    Appointment,
    CheckIn,
    Escalation,
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
    EscalationStatus,
    StepCategory,
    TaskStatus,
    TimelineEventStatus,
)
from prefix_api.domain.errors import ConflictError, NotFoundError
from prefix_api.domain.permissions import Permission
from prefix_api.domain.portal import StepState, step_view
from prefix_api.domain.principal import StaffPrincipal
from prefix_api.domain.risk import RiskResult
from prefix_api.services.audit import record_audit
from prefix_api.services.risk import compute as compute_risk

PURPOSE_LIST = "dashboard_list"
PURPOSE_DRAWER = "dashboard_patient_drawer"
PURPOSE_RESEND = "dashboard_resend_instructions"
PURPOSE_QUEUE = "dashboard_task_queue"
DUE_SOON = dt.timedelta(hours=1)
_CLOSED = (AppointmentStatus.CANCELLED, AppointmentStatus.COMPLETED)
_OPEN_TASKS = (TaskStatus.OPEN, TaskStatus.IN_PROGRESS)


@dataclass(frozen=True, slots=True)
class UpcomingRow:
    appointment: Appointment
    patient: Patient
    procedure_name: str
    facility_name: str
    required_steps: int
    confirmed_steps: int
    problem_steps: int
    open_escalations: int
    open_tasks: int
    risk: RiskResult

    @property
    def readiness(self) -> int:
        """Share of the steps that need confirmation which are done; 100 when none need it."""
        if self.required_steps == 0:
            return 100
        return round(100 * self.confirmed_steps / self.required_steps)


@dataclass(frozen=True, slots=True)
class DrawerStep:
    event: PatientTimelineEvent
    title: str
    requires_confirmation: bool
    is_critical: bool
    response: CheckInResponse | None
    category: StepCategory
    # The state the patient sees in the portal, so staff and patient never disagree.
    state: StepState


@dataclass(frozen=True, slots=True)
class Drawer:
    row: UpcomingRow
    steps: list[DrawerStep]
    messages: list[Message]
    escalations: list[Escalation]
    tasks: list[Task]


@dataclass(frozen=True, slots=True)
class QueueItem:
    task: Task
    patient_name: str
    sla: str  # "overdue", "due_soon" or "on_time"


def _sla(task: Task, now: dt.datetime) -> str:
    if task.due_at is None:
        return "on_time"
    if task.due_at < now:
        return "overdue"
    if task.due_at < now + DUE_SOON:
        return "due_soon"
    return "on_time"


class DashboardService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def upcoming(
        self, principal: StaffPrincipal, *, now: dt.datetime, hours: int = 72, limit: int = 200
    ) -> list[UpcomingRow]:
        principal.require(Permission.APPOINTMENT_READ)
        principal.require(Permission.PATIENT_READ)
        rows = self._session.execute(
            select(Appointment, Patient, ProcedureType.name, Facility.name)
            .join(Patient, Patient.id == Appointment.patient_id)
            .join(ProcedureType, ProcedureType.id == Appointment.procedure_type_id)
            .join(Facility, Facility.id == Appointment.facility_id)
            .where(
                Appointment.organization_id == principal.organization_id,
                Appointment.scheduled_at >= now,
                Appointment.scheduled_at < now + dt.timedelta(hours=hours),
                Appointment.status.not_in(_CLOSED),
            )
            .order_by(Appointment.scheduled_at)
            .limit(limit)
        ).all()
        if not rows:
            return []
        ids = [appointment.id for appointment, *_ in rows]
        required, confirmed = self._step_counts(ids)
        problems = self._problem_counts(ids)
        escalations = self._open_escalations(ids)
        tasks = self._open_tasks(ids)

        result: list[UpcomingRow] = []
        for appointment, patient, procedure_name, facility_name in rows:
            record_audit(
                self._session,
                principal=principal,
                action=AuditAction.LIST,
                entity_type="appointment",
                entity_id=appointment.id,
                patient_id=patient.id,
                purpose=PURPOSE_LIST,
            )
            result.append(
                UpcomingRow(
                    appointment=appointment,
                    patient=patient,
                    procedure_name=procedure_name,
                    facility_name=facility_name,
                    required_steps=required[appointment.id],
                    confirmed_steps=confirmed[appointment.id],
                    problem_steps=problems[appointment.id],
                    open_escalations=escalations[appointment.id],
                    open_tasks=tasks[appointment.id],
                    risk=compute_risk(self._session, appointment, now=now),
                )
            )
        result.sort(
            key=lambda row: (
                row.open_escalations == 0,
                -row.risk.score,
                row.readiness,
                row.appointment.scheduled_at,
            )
        )
        return result

    def drawer(
        self, principal: StaffPrincipal, appointment_id: uuid.UUID, *, now: dt.datetime
    ) -> Drawer:
        principal.require(Permission.APPOINTMENT_READ)
        principal.require(Permission.PATIENT_READ)
        appointment = self._session.scalar(
            select(Appointment).where(
                Appointment.id == appointment_id,
                Appointment.organization_id == principal.organization_id,
            )
        )
        if appointment is None:
            raise NotFoundError("Appointment not found")
        summary = self.upcoming_for(principal, appointment, now=now)
        step_rows = self._session.execute(
            select(PatientTimelineEvent, PrepStep, CheckIn.response)
            .join(PrepStep, PrepStep.id == PatientTimelineEvent.step_id)
            .outerjoin(CheckIn, CheckIn.timeline_event_id == PatientTimelineEvent.id)
            .where(
                PatientTimelineEvent.appointment_id == appointment.id,
                PatientTimelineEvent.status != TimelineEventStatus.CANCELLED,
            )
            .order_by(PatientTimelineEvent.due_at, PrepStep.sort_order)
        ).all()
        steps = [
            DrawerStep(
                event=event,
                title=step.title,
                requires_confirmation=step.requires_confirmation,
                is_critical=step.is_critical,
                response=response,
                category=step.category,
                state=step_view(
                    status=event.status,
                    requires_confirmation=step.requires_confirmation,
                    send_at=event.send_at,
                    due_at=event.due_at,
                    last_response=response,
                    now=now,
                ).state,
            )
            for event, step, response in step_rows
        ]
        messages = list(
            self._session.scalars(
                select(Message)
                .where(Message.appointment_id == appointment.id)
                .order_by(Message.created_at.desc())
                .limit(10)
            )
        )
        escalations = list(
            self._session.scalars(
                select(Escalation)
                .where(Escalation.appointment_id == appointment.id)
                .order_by(Escalation.created_at.desc())
            )
        )
        tasks = list(
            self._session.scalars(
                select(Task)
                .where(Task.appointment_id == appointment.id)
                .order_by(Task.created_at.desc())
            )
        )
        record_audit(
            self._session,
            principal=principal,
            action=AuditAction.READ,
            entity_type="appointment",
            entity_id=appointment.id,
            patient_id=appointment.patient_id,
            purpose=PURPOSE_DRAWER,
        )
        return Drawer(
            row=summary, steps=steps, messages=messages, escalations=escalations, tasks=tasks
        )

    def upcoming_for(
        self, principal: StaffPrincipal, appointment: Appointment, *, now: dt.datetime
    ) -> UpcomingRow:
        """The summary row for one appointment (used by the drawer)."""
        patient = self._session.get(Patient, appointment.patient_id)
        procedure = self._session.get(ProcedureType, appointment.procedure_type_id)
        facility = self._session.get(Facility, appointment.facility_id)
        if patient is None or procedure is None or facility is None:  # pragma: no cover
            raise NotFoundError("Appointment not found")
        ids = [appointment.id]
        required, confirmed = self._step_counts(ids)
        problems = self._problem_counts(ids)
        escalations = self._open_escalations(ids)
        tasks = self._open_tasks(ids)
        return UpcomingRow(
            appointment=appointment,
            patient=patient,
            procedure_name=procedure.name,
            facility_name=facility.name,
            required_steps=required[appointment.id],
            confirmed_steps=confirmed[appointment.id],
            problem_steps=problems[appointment.id],
            open_escalations=escalations[appointment.id],
            open_tasks=tasks[appointment.id],
            risk=compute_risk(self._session, appointment, now=now),
        )

    def queue(
        self, principal: StaffPrincipal, *, now: dt.datetime, limit: int = 200
    ) -> list[QueueItem]:
        """Open and in-progress tasks, most overdue first, each with its SLA state."""
        principal.require(Permission.TASK_MANAGE)
        rows = self._session.execute(
            select(Task, Patient.first_name, Patient.last_name)
            .outerjoin(Patient, Patient.id == Task.patient_id)
            .where(
                Task.organization_id == principal.organization_id,
                Task.status.in_(_OPEN_TASKS),
            )
            .order_by(Task.due_at.asc().nulls_last(), Task.created_at)
            .limit(limit)
        ).all()
        items = []
        for task, first, last in rows:
            if task.patient_id is not None:
                record_audit(
                    self._session,
                    principal=principal,
                    action=AuditAction.LIST,
                    entity_type="task",
                    entity_id=task.id,
                    patient_id=task.patient_id,
                    purpose=PURPOSE_QUEUE,
                )
            name = f"{first} {last}" if first else "No patient"
            items.append(QueueItem(task=task, patient_name=name, sla=_sla(task, now)))
        return items

    def resend_failed(
        self, principal: StaffPrincipal, appointment_id: uuid.UUID, *, now: dt.datetime
    ) -> int:
        """Queue the reminders that failed to send so the dispatcher tries them again.

        Only failed reminders are retried. A reminder that was sent is never sent again, so
        the patient cannot receive the same instruction twice.
        """
        principal.require(Permission.APPOINTMENT_WRITE)
        appointment = self._session.scalar(
            select(Appointment)
            .where(
                Appointment.id == appointment_id,
                Appointment.organization_id == principal.organization_id,
            )
            .with_for_update()
        )
        if appointment is None:
            raise NotFoundError("Appointment not found")
        if appointment.status in _CLOSED:
            raise ConflictError("A closed appointment has nothing to resend")
        events = list(
            self._session.scalars(
                select(PatientTimelineEvent)
                .where(
                    PatientTimelineEvent.appointment_id == appointment.id,
                    PatientTimelineEvent.status == TimelineEventStatus.FAILED,
                )
                .with_for_update()
            )
        )
        for event in events:
            event.status = TimelineEventStatus.PENDING
            event.send_at = now
            event.last_error = None
        record_audit(
            self._session,
            principal=principal,
            action=AuditAction.UPDATE,
            entity_type="appointment",
            entity_id=appointment.id,
            patient_id=appointment.patient_id,
            purpose=PURPOSE_RESEND,
            details={"count": len(events)},
        )
        return len(events)

    # -- counts ---------------------------------------------------------------------------

    def _step_counts(self, ids: list[uuid.UUID]) -> tuple[Counter[uuid.UUID], Counter[uuid.UUID]]:
        rows = self._session.execute(
            select(
                PatientTimelineEvent.appointment_id,
                PatientTimelineEvent.status,
                PrepStep.requires_confirmation,
            )
            .join(PrepStep, PrepStep.id == PatientTimelineEvent.step_id)
            .where(
                PatientTimelineEvent.appointment_id.in_(ids),
                PatientTimelineEvent.status != TimelineEventStatus.CANCELLED,
            )
        ).all()
        required: Counter[uuid.UUID] = Counter(dict.fromkeys(ids, 0))
        confirmed: Counter[uuid.UUID] = Counter(dict.fromkeys(ids, 0))
        for appointment_id, status, needs in rows:
            if not needs:
                continue
            required[appointment_id] += 1
            if status is TimelineEventStatus.CONFIRMED:
                confirmed[appointment_id] += 1
        return required, confirmed

    def _problem_counts(self, ids: list[uuid.UUID]) -> Counter[uuid.UUID]:
        rows = self._session.execute(
            select(CheckIn.appointment_id, func.count())
            .where(
                CheckIn.appointment_id.in_(ids),
                CheckIn.response.in_([CheckInResponse.NO, CheckInResponse.HELP]),
            )
            .group_by(CheckIn.appointment_id)
        ).all()
        counts: Counter[uuid.UUID] = Counter(dict.fromkeys(ids, 0))
        counts.update(dict(rows))
        return counts

    def _open_escalations(self, ids: list[uuid.UUID]) -> Counter[uuid.UUID]:
        rows = self._session.execute(
            select(Escalation.appointment_id, func.count())
            .where(
                Escalation.appointment_id.in_(ids),
                Escalation.status != EscalationStatus.RESOLVED,
            )
            .group_by(Escalation.appointment_id)
        ).all()
        counts: Counter[uuid.UUID] = Counter(dict.fromkeys(ids, 0))
        counts.update({row[0]: row[1] for row in rows if row[0] is not None})
        return counts

    def _open_tasks(self, ids: list[uuid.UUID]) -> Counter[uuid.UUID]:
        rows = self._session.execute(
            select(Task.appointment_id, func.count())
            .where(Task.appointment_id.in_(ids), Task.status.in_(_OPEN_TASKS))
            .group_by(Task.appointment_id)
        ).all()
        counts: Counter[uuid.UUID] = Counter(dict.fromkeys(ids, 0))
        counts.update({row[0]: row[1] for row in rows if row[0] is not None})
        return counts
