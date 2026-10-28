"""Coordinator dashboard: what is shown, in which order, and who may see it."""

import datetime as dt

from api_testkit import Builder, staff_headers
from fastapi.testclient import TestClient
from messaging_testkit import Booked, book
from sqlalchemy.orm import Session

from prefix_api.core.config import Settings
from prefix_api.db.models import Organization, Task
from prefix_api.domain.enums import (
    EscalationSeverity,
    EscalationSource,
    Role,
    TaskStatus,
    TaskType,
    TimelineEventStatus,
)
from prefix_api.domain.principal import StaffPrincipal, SystemPrincipal
from prefix_api.schemas.appointments import AppointmentCreate
from prefix_api.services.appointments import AppointmentService
from prefix_api.services.check_ins import create_escalation


def staff_for(
    build: Builder,
    db_session: Session,
    booked: Booked,
    settings: Settings,
    role: Role = Role.COORDINATOR,
) -> dict[str, str]:
    org = db_session.get(Organization, booked.patient.organization_id)
    assert org is not None
    return staff_headers(settings, build.user(org, role))


def second_booking(build: Builder, db_session: Session, booked: Booked, days_ahead: int) -> Booked:
    """Another patient booked into the same hospital and procedure as ``booked``."""
    org = db_session.get(Organization, booked.patient.organization_id)
    assert org is not None
    patient = build.patient(org)
    coordinator = build.user(org, Role.COORDINATOR)
    principal = StaffPrincipal(
        user_id=coordinator.id, organization_id=org.id, role=Role.COORDINATOR
    )
    now = dt.datetime.now(dt.UTC)
    appointment = AppointmentService(db_session).create(
        principal,
        AppointmentCreate(
            patient_id=patient.id,
            facility_id=booked.appointment.facility_id,
            procedure_type_id=booked.appointment.procedure_type_id,
            scheduled_at=now + dt.timedelta(days=days_ahead),
        ),
        now=now,
    )
    db_session.flush()
    return Booked(appointment=appointment, patient=patient, events={})


def upcoming(client: TestClient, headers: dict[str, str]) -> list[dict[str, object]]:
    response = client.get("/dashboard/upcoming", headers=headers)
    assert response.status_code == 200, response.text
    result: list[dict[str, object]] = response.json()
    return result


def test_only_procedures_in_the_next_72_hours_are_listed(
    client: TestClient, settings: Settings, build: Builder, db_session: Session
) -> None:
    soon = book(build, db_session, days_ahead=1)
    later = book(build, db_session, days_ahead=10)

    ids = [
        row["appointment_id"]
        for row in upcoming(client, staff_for(build, db_session, soon, settings))
    ]

    assert str(soon.appointment.id) in ids
    assert str(later.appointment.id) not in ids


def test_escalated_patients_come_first_then_the_least_ready(
    client: TestClient, settings: Settings, build: Builder, db_session: Session
) -> None:
    ready = book(build, db_session, days_ahead=1)
    for event in ready.events.values():
        event.status = TimelineEventStatus.CONFIRMED
    db_session.flush()
    stuck = second_booking(build, db_session, ready, days_ahead=1)  # nothing confirmed
    flagged = second_booking(build, db_session, ready, days_ahead=2)  # later, but escalated
    create_escalation(
        db_session,
        principal=SystemPrincipal(organization_id=ready.patient.organization_id, job="test"),
        patient=flagged.patient,
        appointment=flagged.appointment,
        severity=EscalationSeverity.URGENT,
        summary="Chest pain",
        purpose="test",
        source=EscalationSource.RED_FLAG,
    )
    db_session.flush()

    order = [
        row["appointment_id"]
        for row in upcoming(client, staff_for(build, db_session, ready, settings))
    ]

    assert order.index(str(flagged.appointment.id)) < order.index(str(stuck.appointment.id))
    assert order.index(str(stuck.appointment.id)) < order.index(str(ready.appointment.id))


def test_readiness_counts_only_steps_that_need_confirmation(
    client: TestClient, settings: Settings, build: Builder, db_session: Session
) -> None:
    booked = book(build, db_session, days_ahead=1)
    booked.events["Arrange escort"].status = TimelineEventStatus.CONFIRMED
    booked.events["Clear liquids"].status = TimelineEventStatus.CONFIRMED
    db_session.flush()

    row = next(
        r
        for r in upcoming(client, staff_for(build, db_session, booked, settings))
        if r["appointment_id"] == str(booked.appointment.id)
    )

    assert row["required_steps"] == 2
    assert row["confirmed_steps"] == 2
    assert row["readiness"] == 100


def test_the_drawer_shows_the_timeline_and_is_audited(
    client: TestClient, settings: Settings, build: Builder, db_session: Session
) -> None:
    booked = book(build, db_session, days_ahead=1)

    response = client.get(
        f"/dashboard/appointments/{booked.appointment.id}",
        headers=staff_for(build, db_session, booked, settings),
    )

    assert response.status_code == 200
    body = response.json()
    assert (
        body["appointment"]["patient_name"]
        == f"{booked.patient.first_name} {booked.patient.last_name}"
    )
    assert {step["title"] for step in body["steps"]} == {
        "Low-fibre diet",
        "Arrange escort",
        "Clear liquids",
    }


def test_another_hospitals_drawer_is_not_found(
    client: TestClient, settings: Settings, build: Builder, db_session: Session
) -> None:
    ours = book(build, db_session, days_ahead=1)
    theirs = book(build, db_session, days_ahead=1)

    response = client.get(
        f"/dashboard/appointments/{theirs.appointment.id}",
        headers=staff_for(build, db_session, ours, settings),
    )

    assert response.status_code == 404


def test_the_task_queue_shows_each_tasks_sla(
    client: TestClient, settings: Settings, build: Builder, db_session: Session
) -> None:
    booked = book(build, db_session, days_ahead=1)
    now = dt.datetime.now(dt.UTC)
    for title, due in (
        ("Overdue call", now - dt.timedelta(hours=2)),
        ("Due soon call", now + dt.timedelta(minutes=20)),
        ("Later call", now + dt.timedelta(hours=5)),
    ):
        db_session.add(
            Task(
                organization_id=booked.patient.organization_id,
                type=TaskType.CALL_PATIENT,
                title=title,
                patient_id=booked.patient.id,
                due_at=due,
            )
        )
    db_session.flush()

    response = client.get(
        "/dashboard/queue", headers=staff_for(build, db_session, booked, settings)
    )

    assert response.status_code == 200
    sla = {item["title"]: item["sla"] for item in response.json()}
    assert sla["Overdue call"] == "overdue"
    assert sla["Due soon call"] == "due_soon"
    assert sla["Later call"] == "on_time"


def test_resending_only_retries_failed_reminders(
    client: TestClient, settings: Settings, build: Builder, db_session: Session
) -> None:
    booked = book(build, db_session, days_ahead=1)
    booked.events["Low-fibre diet"].status = TimelineEventStatus.FAILED
    booked.events["Clear liquids"].status = TimelineEventStatus.SENT
    db_session.flush()

    response = client.post(
        f"/dashboard/appointments/{booked.appointment.id}/resend-failed",
        headers=staff_for(build, db_session, booked, settings),
    )

    assert response.status_code == 200
    assert response.json() == {"queued": 1}
    db_session.refresh(booked.events["Low-fibre diet"])
    db_session.refresh(booked.events["Clear liquids"])
    assert booked.events["Low-fibre diet"].status is TimelineEventStatus.PENDING
    assert booked.events["Clear liquids"].status is TimelineEventStatus.SENT


def test_viewers_cannot_open_the_dashboard(
    client: TestClient, settings: Settings, build: Builder, db_session: Session
) -> None:
    booked = book(build, db_session, days_ahead=1)

    response = client.get(
        "/dashboard/upcoming",
        headers=staff_for(build, db_session, booked, settings, Role.VIEWER),
    )

    assert response.status_code == 403


def test_only_open_tasks_are_in_the_queue(
    client: TestClient, settings: Settings, build: Builder, db_session: Session
) -> None:
    booked = book(build, db_session, days_ahead=1)
    db_session.add(
        Task(
            organization_id=booked.patient.organization_id,
            type=TaskType.CALL_PATIENT,
            title="Done already",
            patient_id=booked.patient.id,
            status=TaskStatus.DONE,
        )
    )
    db_session.flush()

    response = client.get(
        "/dashboard/queue", headers=staff_for(build, db_session, booked, settings)
    )

    assert "Done already" not in [item["title"] for item in response.json()]
