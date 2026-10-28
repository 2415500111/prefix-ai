"""Cancellation risk v1: the rules, the stored scores, and what a HIGH score does."""

import dataclasses
import datetime as dt

from api_testkit import Builder, staff_headers
from fastapi.testclient import TestClient
from messaging_testkit import Booked, book
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from prefix_api.core.config import Settings
from prefix_api.db.models import Organization, RiskScore, Task
from prefix_api.domain.enums import (
    EscalationSeverity,
    EscalationSource,
    RiskLevel,
    Role,
    TaskType,
)
from prefix_api.domain.principal import SystemPrincipal
from prefix_api.domain.risk import RiskInputs, score
from prefix_api.services.check_ins import create_escalation
from prefix_api.services.risk import refresh

Factory = sessionmaker[Session]

QUIET = RiskInputs(
    unconfirmed_steps=0,
    logistics_unconfirmed=False,
    problem_replies=0,
    open_escalations=0,
    urgent_escalation=False,
    on_anticoagulant=False,
    diabetic_on_insulin=False,
    on_glp1_agonist=False,
    contrast_allergy=False,
    metal_implant=False,
    egfr=None,
    procedure_code="COLONOSCOPY",
    hours_to_procedure=100,
)


def inputs(**changes: object) -> RiskInputs:
    return dataclasses.replace(QUIET, **changes)  # type: ignore[arg-type]


def test_nothing_outstanding_is_low_risk() -> None:
    result = score(QUIET)

    assert result.score == 0
    assert result.level is RiskLevel.LOW
    assert result.factors == ()


def test_each_reason_says_why_and_how_many_points_it_adds() -> None:
    result = score(inputs(unconfirmed_steps=2, on_anticoagulant=True))

    labels = {f.feature: (f.points, f.label) for f in result.factors}
    assert labels["unconfirmed_steps"] == (16, "2 prep steps not yet confirmed")
    assert labels["anticoagulant"] == (10, "Takes a blood thinner (anticoagulant)")
    assert result.score == 26
    assert result.level is RiskLevel.MEDIUM


def test_the_score_is_capped_and_high_risk_needs_fifty() -> None:
    result = score(
        inputs(
            unconfirmed_steps=5,
            logistics_unconfirmed=True,
            problem_replies=2,
            open_escalations=2,
            urgent_escalation=True,
            on_anticoagulant=True,
            diabetic_on_insulin=True,
        )
    )

    assert result.score == 100
    assert result.level is RiskLevel.HIGH
    assert result.factors[0].points >= result.factors[-1].points  # strongest reason first


def test_site_specific_rules_only_apply_to_their_procedure() -> None:
    contrast_allergy = inputs(contrast_allergy=True, procedure_code="CT_CONTRAST")
    metal = inputs(metal_implant=True, procedure_code="MRI")

    def features(r: RiskInputs) -> set[str]:
        return {f.feature for f in score(r).factors}

    assert "contrast_allergy" not in features(inputs(contrast_allergy=True))
    assert "metal_implant" not in features(inputs(metal_implant=True))
    assert "contrast_allergy" in features(contrast_allergy)
    assert "metal_implant" in features(metal)


def test_low_kidney_function_matters_for_contrast_scans_only() -> None:
    ct = inputs(egfr=22.0, procedure_code="CT_CONTRAST")
    colonoscopy = inputs(egfr=22.0)

    assert "low_egfr" in {f.feature for f in score(ct).factors}
    assert "low_egfr" not in {f.feature for f in score(colonoscopy).factors}


def test_the_last_day_adds_risk_only_while_steps_are_outstanding() -> None:
    soon_with_steps = inputs(unconfirmed_steps=1, hours_to_procedure=10)
    soon_all_done = inputs(hours_to_procedure=10)

    assert "soon" in {f.feature for f in score(soon_with_steps).factors}
    assert "soon" not in {f.feature for f in score(soon_all_done).factors}


def high_risk_booking(build: Builder, db_session: Session) -> Booked:
    """A procedure tomorrow: steps outstanding, a blood thinner, an urgent escalation."""
    booked = book(build, db_session, days_ahead=1)
    booked.patient.on_anticoagulant = True
    booked.patient.diabetic_on_insulin = True
    create_escalation(
        db_session,
        principal=SystemPrincipal(organization_id=booked.patient.organization_id, job="test"),
        patient=booked.patient,
        appointment=booked.appointment,
        severity=EscalationSeverity.URGENT,
        summary="Chest pain",
        purpose="test",
        source=EscalationSource.RED_FLAG,
    )
    db_session.flush()
    return booked


def test_refresh_stores_every_score_and_opens_one_task_for_a_high_risk_procedure(
    build: Builder, db_session: Session, session_factory: Factory
) -> None:
    booked = high_risk_booking(build, db_session)
    now = dt.datetime.now(dt.UTC)

    first = refresh(session_factory, now=now)
    second = refresh(session_factory, now=now)

    assert first.high >= 1
    assert first.tasks_opened == 1
    assert second.tasks_opened == 0, "an open review task must not be duplicated"
    stored = db_session.scalars(
        select(RiskScore).where(RiskScore.appointment_id == booked.appointment.id)
    ).all()
    assert len(stored) == 2
    assert stored[0].model_version == "rules-v1"
    review = db_session.scalars(
        select(Task).where(
            Task.appointment_id == booked.appointment.id, Task.type == TaskType.REVIEW_RISK
        )
    ).all()
    assert len(review) == 1
    assert review[0].title.startswith("High cancellation risk")


def test_the_dashboard_explains_the_score_in_words(
    client: TestClient, settings: Settings, build: Builder, db_session: Session
) -> None:
    booked = high_risk_booking(build, db_session)
    org = db_session.get(Organization, booked.patient.organization_id)
    assert org is not None
    headers = staff_headers(settings, build.user(org, Role.COORDINATOR))

    row = next(
        r
        for r in client.get("/dashboard/upcoming", headers=headers).json()
        if r["appointment_id"] == str(booked.appointment.id)
    )

    assert row["risk_level"] == "HIGH"
    assert row["risk_score"] >= 50
    assert any("blood thinner" in reason for reason in row["risk_reasons"])
    assert any("Urgent escalation" in reason for reason in row["risk_reasons"])


def test_escalated_then_riskiest_patients_come_first(
    client: TestClient, settings: Settings, build: Builder, db_session: Session
) -> None:
    risky = high_risk_booking(build, db_session)
    org = db_session.get(Organization, risky.patient.organization_id)
    assert org is not None
    calm = book(build, db_session, days_ahead=1)
    # Move the calm booking into the risky booking's hospital so the coordinator sees both.
    calm.patient.organization_id = org.id
    calm.appointment.organization_id = org.id
    db_session.flush()
    headers = staff_headers(settings, build.user(org, Role.COORDINATOR))

    order = [r["appointment_id"] for r in client.get("/dashboard/upcoming", headers=headers).json()]

    assert order.index(str(risky.appointment.id)) < order.index(str(calm.appointment.id))
