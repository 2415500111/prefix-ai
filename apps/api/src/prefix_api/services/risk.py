"""Cancellation risk for upcoming procedures: gather the facts, score them, record, and act.

``refresh`` runs every 15 minutes in the worker. It stores each score (so changes can be
audited) and opens one coordinator task per procedure that becomes HIGH risk. The dashboard
computes the score on the fly, so what it shows is always current.
"""

import datetime as dt
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from prefix_api.db.models import (
    Appointment,
    CheckIn,
    Escalation,
    Organization,
    Patient,
    PatientTimelineEvent,
    PrepStep,
    ProcedureType,
    RiskScore,
    Task,
)
from prefix_api.domain.enums import (
    AppointmentStatus,
    AuditAction,
    CheckInResponse,
    EscalationSeverity,
    EscalationStatus,
    RiskLevel,
    StepCategory,
    TaskStatus,
    TaskType,
    TimelineEventStatus,
)
from prefix_api.domain.principal import SystemPrincipal
from prefix_api.domain.risk import MODEL_VERSION, RiskInputs, RiskResult, score
from prefix_api.services.audit import record_audit
from prefix_api.services.check_ins import create_task

JOB = "risk_refresh"
WINDOW = dt.timedelta(hours=72)
_CLOSED = (AppointmentStatus.CANCELLED, AppointmentStatus.COMPLETED)
_OPEN_TASKS = (TaskStatus.OPEN, TaskStatus.IN_PROGRESS)
_HIGH_TASK_DUE = dt.timedelta(hours=1)


@dataclass(frozen=True, slots=True)
class RefreshResult:
    scored: int
    high: int
    tasks_opened: int


def gather(session: Session, appointment: Appointment, *, now: dt.datetime) -> RiskInputs:
    """The facts the rules need, read from the database for one procedure."""
    steps = session.execute(
        select(PatientTimelineEvent.status, PrepStep.requires_confirmation, PrepStep.category)
        .join(PrepStep, PrepStep.id == PatientTimelineEvent.step_id)
        .where(
            PatientTimelineEvent.appointment_id == appointment.id,
            PatientTimelineEvent.status != TimelineEventStatus.CANCELLED,
        )
    ).all()
    outstanding = [
        category
        for status, needs, category in steps
        if needs and status is not TimelineEventStatus.CONFIRMED
    ]
    problem_count = len(
        session.scalars(
            select(CheckIn.id).where(
                CheckIn.appointment_id == appointment.id,
                CheckIn.response.in_([CheckInResponse.NO, CheckInResponse.HELP]),
            )
        ).all()
    )
    escalations = session.scalars(
        select(Escalation).where(
            Escalation.appointment_id == appointment.id,
            Escalation.status != EscalationStatus.RESOLVED,
        )
    ).all()
    patient = session.get(Patient, appointment.patient_id)
    procedure = session.get(ProcedureType, appointment.procedure_type_id)
    if patient is None or procedure is None:  # pragma: no cover - foreign keys prevent this
        raise LookupError("appointment without patient or procedure")
    return RiskInputs(
        unconfirmed_steps=len(outstanding),
        logistics_unconfirmed=any(c is StepCategory.LOGISTICS for c in outstanding),
        problem_replies=problem_count,
        open_escalations=len(escalations),
        urgent_escalation=any(e.severity is EscalationSeverity.URGENT for e in escalations),
        on_anticoagulant=patient.on_anticoagulant,
        diabetic_on_insulin=patient.diabetic_on_insulin,
        on_glp1_agonist=patient.on_glp1_agonist,
        contrast_allergy=patient.has_contrast_allergy,
        metal_implant=patient.has_metal_implant,
        egfr=float(patient.egfr_value) if patient.egfr_value is not None else None,
        procedure_code=procedure.code,
        hours_to_procedure=(appointment.scheduled_at - now).total_seconds() / 3600,
    )


def compute(session: Session, appointment: Appointment, *, now: dt.datetime) -> RiskResult:
    return score(gather(session, appointment, now=now))


def refresh(session_factory: sessionmaker[Session], *, now: dt.datetime) -> RefreshResult:
    """Score every upcoming procedure in every hospital; open a task for each new HIGH one."""
    scored = high = opened = 0
    with session_factory() as session:
        appointments = session.scalars(
            select(Appointment).where(
                Appointment.scheduled_at >= now,
                Appointment.scheduled_at < now + WINDOW,
                Appointment.status.not_in(_CLOSED),
            )
        ).all()
        for appointment in appointments:
            result = compute(session, appointment, now=now)
            session.add(
                RiskScore(
                    organization_id=appointment.organization_id,
                    appointment_id=appointment.id,
                    score=result.score,
                    level=result.level,
                    factors=[
                        {"feature": f.feature, "weight": f.points, "label": f.label}
                        for f in result.factors
                    ],
                    model_version=MODEL_VERSION,
                    computed_at=now,
                )
            )
            scored += 1
            if result.level is RiskLevel.HIGH:
                high += 1
                if _open_review(session, appointment.id) is None:
                    _open_high_risk_task(session, appointment, result, now)
                    opened += 1
            session.commit()
    return RefreshResult(scored=scored, high=high, tasks_opened=opened)


def _open_review(session: Session, appointment_id: uuid.UUID) -> Task | None:
    return session.scalar(
        select(Task).where(
            Task.appointment_id == appointment_id,
            Task.type == TaskType.REVIEW_RISK,
            Task.status.in_(_OPEN_TASKS),
        )
    )


def _open_high_risk_task(
    session: Session, appointment: Appointment, result: RiskResult, now: dt.datetime
) -> None:
    patient = session.get(Patient, appointment.patient_id)
    organization = session.get(Organization, appointment.organization_id)
    if patient is None or organization is None:  # pragma: no cover
        return
    reasons = "; ".join(f.label for f in result.factors[:3])
    task = create_task(
        session,
        patient=patient,
        appointment_id=appointment.id,
        task_type=TaskType.REVIEW_RISK,
        title=f"High cancellation risk ({result.score}): {reasons}"[:300],
        now=now,
        due_in=_HIGH_TASK_DUE,
    )
    session.flush()
    record_audit(
        session,
        principal=SystemPrincipal(organization_id=organization.id, job=JOB),
        action=AuditAction.CREATE,
        entity_type="task",
        entity_id=task.id,
        patient_id=patient.id,
        purpose="risk_review",
        details={"count": result.score},
    )
