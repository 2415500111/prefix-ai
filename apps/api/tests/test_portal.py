"""The patient portal: patients see only their own prep, and their answers reach staff."""

import datetime as dt
from collections.abc import Callable
from typing import Any

import pytest
from api_testkit import Builder, patient_headers, staff_headers
from fastapi import FastAPI
from fastapi.testclient import TestClient
from messaging_testkit import Booked, FakeTranslator, RecordingProvider, book
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from prefix_api.api.deps import utcnow
from prefix_api.core.config import Settings
from prefix_api.db.models import AuditLog, CheckIn, Escalation, Message, Task
from prefix_api.domain.enums import (
    ActorType,
    AppointmentStatus,
    AuditAction,
    CheckInResponse,
    EscalationSeverity,
    MessageChannel,
    MessageDirection,
    Role,
    TaskType,
    TimelineEventStatus,
)
from prefix_api.domain.portal import StepState, step_view
from prefix_api.services.dispatch import dispatch_due_reminders

Clock = Callable[[dt.datetime], None]


@pytest.fixture
def set_now(app: FastAPI) -> Clock:
    def set_to(at: dt.datetime) -> None:
        app.dependency_overrides[utcnow] = lambda: at

    return set_to


class Portal:
    def __init__(self, client: TestClient, settings: Settings, booked: Booked) -> None:
        self.client = client
        self.booked = booked
        self.headers = patient_headers(settings, booked.patient)

    def appointments(self) -> list[dict[str, Any]]:
        response = self.client.get("/patient/appointments", headers=self.headers)
        assert response.status_code == 200, response.text
        result: list[dict[str, Any]] = response.json()
        return result

    def step(self, title: str) -> dict[str, Any]:
        [appointment] = self.appointments()
        return next(s for s in appointment["steps"] if s["title"] == title)

    def confirm(self, title: str) -> int:
        event_id = self.booked.events[title].id
        return self.client.post(
            f"/patient/steps/{event_id}/confirm", headers=self.headers
        ).status_code

    def problem(self, title: str, note: str | None = None) -> int:
        event_id = self.booked.events[title].id
        return self.client.post(
            f"/patient/steps/{event_id}/problem", headers=self.headers, json={"note": note}
        ).status_code

    def reschedule(self, note: str | None = None) -> int:
        appointment_id = self.booked.appointment.id
        return self.client.post(
            f"/patient/appointments/{appointment_id}/reschedule-request",
            headers=self.headers,
            json={"note": note},
        ).status_code


@pytest.fixture
def portal(client: TestClient, settings: Settings, build: Builder, db_session: Session) -> Portal:
    return Portal(client, settings, book(build, db_session))


def reminder_time(portal: Portal, title: str) -> dt.datetime:
    return portal.booked.events[title].send_at + dt.timedelta(minutes=1)


def test_patient_sees_their_procedure_and_steps(portal: Portal, db_session: Session) -> None:
    [appointment] = portal.appointments()

    assert appointment["procedure_name"] == "Colonoscopy"
    assert appointment["facility"]["timezone"] == "Asia/Kolkata"
    assert [s["title"] for s in appointment["steps"]] == [
        "Low-fibre diet",
        "Arrange escort",
        "Clear liquids",
    ]
    assert {s["state"] for s in appointment["steps"]} == {"UPCOMING"}
    assert appointment["steps"][0]["instruction"] == "Instruction for Low-fibre diet."
    assert appointment["reschedule_requested"] is False
    reads = db_session.scalars(
        select(AuditLog).where(
            AuditLog.patient_id == portal.booked.patient.id,
            AuditLog.actor_type == ActorType.PATIENT,
            AuditLog.action == AuditAction.READ,
        )
    ).all()
    assert [r.entity_type for r in reads] == ["appointment"]


def test_steps_cannot_be_confirmed_before_their_reminder_time(portal: Portal) -> None:
    assert portal.step("Arrange escort")["can_confirm"] is False
    assert portal.confirm("Arrange escort") == 409


def test_confirming_a_due_step(portal: Portal, set_now: Clock, db_session: Session) -> None:
    set_now(reminder_time(portal, "Arrange escort"))
    assert portal.step("Arrange escort")["state"] == "DUE"

    assert portal.confirm("Arrange escort") == 204

    step = portal.step("Arrange escort")
    assert step["state"] == "DONE"
    assert step["can_confirm"] is False
    event = portal.booked.events["Arrange escort"]
    db_session.refresh(event)
    assert event.status is TimelineEventStatus.CONFIRMED
    check_in = db_session.scalar(select(CheckIn).where(CheckIn.timeline_event_id == event.id))
    assert check_in is not None
    assert check_in.response is CheckInResponse.YES


def test_portal_answer_closes_the_check_in_the_sms_reminder_opened(
    portal: Portal, set_now: Clock, db_session: Session, session_factory: sessionmaker[Session]
) -> None:
    at = reminder_time(portal, "Arrange escort")
    dispatch_due_reminders(
        session_factory, RecordingProvider(), FakeTranslator(), now=at, batch_size=50
    )
    set_now(at)

    assert portal.confirm("Arrange escort") == 204

    event = portal.booked.events["Arrange escort"]
    check_ins = db_session.scalars(
        select(CheckIn).where(CheckIn.timeline_event_id == event.id)
    ).all()
    assert len(check_ins) == 1
    assert check_ins[0].sent_at is not None
    assert check_ins[0].response is CheckInResponse.YES


def test_problem_with_a_critical_step_escalates_and_flags_the_appointment(
    portal: Portal, db_session: Session
) -> None:
    assert portal.problem("Clear liquids", note="I cannot get the prep solution") == 204

    booked = portal.booked
    db_session.refresh(booked.appointment)
    assert booked.appointment.status is AppointmentStatus.AT_RISK
    escalation = db_session.scalar(
        select(Escalation).where(Escalation.patient_id == booked.patient.id)
    )
    assert escalation is not None
    assert escalation.severity is EscalationSeverity.HIGH
    assert "Clear liquids" in escalation.summary
    assert "I cannot get the prep solution" in escalation.summary
    task = db_session.scalar(select(Task).where(Task.patient_id == booked.patient.id))
    assert task is not None
    assert task.type is TaskType.CALL_PATIENT
    assert task.escalation_id == escalation.id
    assert "prep solution" not in task.title

    step = portal.step("Clear liquids")
    assert step["state"] == "PROBLEM"
    assert step["can_report_problem"] is False
    assert portal.problem("Clear liquids") == 409


def test_problem_with_a_non_critical_step_creates_a_call_task_only(
    portal: Portal, db_session: Session
) -> None:
    assert portal.problem("Arrange escort") == 204

    patient_id = portal.booked.patient.id
    db_session.refresh(portal.booked.appointment)
    assert portal.booked.appointment.status is AppointmentStatus.SCHEDULED
    assert db_session.scalar(select(Escalation).where(Escalation.patient_id == patient_id)) is None
    assert (
        db_session.scalar(select(Task.type).where(Task.patient_id == patient_id))
        is TaskType.CALL_PATIENT
    )


def test_a_step_can_be_confirmed_once_the_problem_is_solved(portal: Portal, set_now: Clock) -> None:
    portal.problem("Arrange escort")
    set_now(reminder_time(portal, "Arrange escort"))

    assert portal.confirm("Arrange escort") == 204
    assert portal.step("Arrange escort")["state"] == "DONE"


def test_reschedule_request_creates_one_task_and_keeps_the_note_encrypted(
    portal: Portal, db_session: Session
) -> None:
    assert portal.reschedule(note="I am travelling that week") == 204
    assert portal.reschedule() == 204

    patient_id = portal.booked.patient.id
    tasks = db_session.scalars(select(Task).where(Task.patient_id == patient_id)).all()
    assert [t.type for t in tasks] == [TaskType.RESCHEDULE]
    message = db_session.scalar(
        select(Message).where(
            Message.patient_id == patient_id, Message.direction == MessageDirection.INBOUND
        )
    )
    assert message is not None
    assert message.channel is MessageChannel.PORTAL
    assert message.body == "I am travelling that week"
    assert portal.appointments()[0]["reschedule_requested"] is True


def test_patients_cannot_see_or_touch_another_patients_prep(
    portal: Portal, client: TestClient, settings: Settings, build: Builder, db_session: Session
) -> None:
    other = Portal(client, settings, book(build, db_session))

    assert len(other.appointments()) == 1
    assert other.appointments()[0]["id"] != str(portal.booked.appointment.id)
    event_id = portal.booked.events["Clear liquids"].id
    response = client.post(f"/patient/steps/{event_id}/problem", headers=other.headers, json={})
    assert response.status_code == 404
    response = client.post(
        f"/patient/appointments/{portal.booked.appointment.id}/reschedule-request",
        headers=other.headers,
        json={},
    )
    assert response.status_code == 404


def test_cancelled_appointments_disappear_and_cannot_be_acted_on(
    portal: Portal, db_session: Session
) -> None:
    portal.booked.appointment.status = AppointmentStatus.CANCELLED
    db_session.flush()

    assert portal.appointments() == []
    assert portal.reschedule() == 409


def test_staff_tokens_are_not_patient_sessions(
    portal: Portal, client: TestClient, settings: Settings, build: Builder
) -> None:
    org = build.organization()
    response = client.get(
        "/patient/appointments", headers=staff_headers(settings, build.user(org, Role.ADMIN))
    )

    assert response.status_code == 401


NOW = dt.datetime(2026, 11, 10, 9, 0, tzinfo=dt.UTC)
HOUR = dt.timedelta(hours=1)


@pytest.mark.parametrize(
    ("status", "confirm", "send_at", "due_at", "response", "expected"),
    [
        (TimelineEventStatus.CONFIRMED, True, -2 * HOUR, -HOUR, None, StepState.DONE),
        (TimelineEventStatus.SENT, True, -2 * HOUR, HOUR, CheckInResponse.NO, StepState.PROBLEM),
        (TimelineEventStatus.SENT, True, -2 * HOUR, -HOUR, None, StepState.OVERDUE),
        (TimelineEventStatus.SENT, True, -2 * HOUR, HOUR, None, StepState.DUE),
        (TimelineEventStatus.PENDING, True, HOUR, 2 * HOUR, None, StepState.UPCOMING),
        # Portal-only patients get no reminder (SKIPPED) but still see the step's state.
        (TimelineEventStatus.SKIPPED, True, -2 * HOUR, -HOUR, None, StepState.OVERDUE),
        (TimelineEventStatus.SENT, False, -2 * HOUR, -HOUR, None, StepState.DONE),
        (TimelineEventStatus.SENT, False, -2 * HOUR, HOUR, None, StepState.DUE),
        (TimelineEventStatus.PENDING, False, HOUR, 2 * HOUR, None, StepState.UPCOMING),
    ],
)
def test_step_states(
    status: TimelineEventStatus,
    confirm: bool,
    send_at: dt.timedelta,
    due_at: dt.timedelta,
    response: CheckInResponse | None,
    expected: StepState,
) -> None:
    view = step_view(
        status=status,
        requires_confirmation=confirm,
        send_at=NOW + send_at,
        due_at=NOW + due_at,
        last_response=response,
        now=NOW,
    )

    assert view.state is expected
    assert view.can_confirm == (confirm and expected not in (StepState.DONE, StepState.UPCOMING))
