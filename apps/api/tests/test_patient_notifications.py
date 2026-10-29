"""The patient's Updates feed: derived from existing records, scoped to the patient, audited."""

import datetime as dt
from collections.abc import Callable
from typing import Any

import pytest
from api_testkit import Builder, patient_headers, staff_headers
from fastapi import FastAPI
from fastapi.testclient import TestClient
from messaging_testkit import Booked, book
from sqlalchemy import select
from sqlalchemy.orm import Session

from prefix_api.api.deps import utcnow
from prefix_api.core.config import Settings
from prefix_api.db.models import AuditLog, Organization, Task
from prefix_api.domain.enums import ActorType, AuditAction, Role, TaskType

Clock = Callable[[dt.datetime], None]


@pytest.fixture
def set_now(app: FastAPI) -> Clock:
    def set_to(at: dt.datetime) -> None:
        app.dependency_overrides[utcnow] = lambda: at

    return set_to


class Updates:
    def __init__(
        self, client: TestClient, settings: Settings, build: Builder, session: Session
    ) -> None:
        self.client = client
        self.booked: Booked = book(build, session)
        self.headers = patient_headers(settings, self.booked.patient)
        org = session.get(Organization, self.booked.patient.organization_id)
        assert org is not None
        self.staff = staff_headers(settings, build.user(org, Role.COORDINATOR))

    def feed(self, lang: str = "en") -> dict[str, Any]:
        response = self.client.get(f"/patient/notifications?lang={lang}", headers=self.headers)
        assert response.status_code == 200, response.text
        result: dict[str, Any] = response.json()
        return result

    def items(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = self.feed()["items"]
        return items

    def read(self, *keys: str) -> Any:
        return self.client.post(
            "/patient/notifications/read", json={"keys": list(keys)}, headers=self.headers
        )

    def staff_post(self, path: str, body: dict[str, Any] | None = None) -> Any:
        response = self.client.post(path, json=body, headers=self.staff)
        assert response.status_code < 300, response.text
        return response.json() if response.content else None


@pytest.fixture
def updates(client: TestClient, settings: Settings, build: Builder, db_session: Session) -> Updates:
    return Updates(client, settings, build, db_session)


def started(updates: Updates, title: str) -> dt.datetime:
    event = updates.booked.events[title]
    return min(event.send_at, event.due_at) + dt.timedelta(minutes=1)


def test_a_new_booking_has_no_updates_and_reading_the_feed_is_audited(
    updates: Updates, db_session: Session
) -> None:
    assert updates.feed() == {"items": [], "unread_count": 0}

    [audit] = db_session.scalars(
        select(AuditLog).where(
            AuditLog.patient_id == updates.booked.patient.id,
            AuditLog.entity_type == "patient_notifications",
        )
    ).all()
    assert audit.action == AuditAction.READ
    assert audit.actor_type == ActorType.PATIENT


def test_steps_that_apply_now_are_listed_newest_first_and_critical_ones_are_urgent(
    updates: Updates, set_now: Clock
) -> None:
    set_now(started(updates, "Clear liquids"))

    feed = updates.feed()

    assert [(i["kind"], i["step_title"], i["urgency"]) for i in feed["items"]] == [
        ("step_now", "Clear liquids", "urgent"),
        ("step_now", "Arrange escort", "normal"),
        ("step_now", "Low-fibre diet", "normal"),
    ]
    assert feed["unread_count"] == 3
    assert feed["items"][0]["key"] == f"step-due:{updates.booked.events['Clear liquids'].id}"
    assert feed["items"][0]["procedure_name"] == "Colonoscopy"
    assert feed["items"][0]["timezone"] == "Asia/Kolkata"


def test_a_step_starting_within_a_day_is_coming_up(updates: Updates, set_now: Clock) -> None:
    set_now(started(updates, "Arrange escort") - dt.timedelta(hours=6))

    kinds = {i["step_title"]: i["kind"] for i in updates.items()}

    assert kinds == {"Arrange escort": "step_soon", "Low-fibre diet": "step_now"}


def test_a_done_step_counts_as_read(updates: Updates, set_now: Clock) -> None:
    set_now(started(updates, "Clear liquids"))
    event_id = updates.booked.events["Clear liquids"].id
    confirmed = updates.client.post(f"/patient/steps/{event_id}/confirm", headers=updates.headers)
    assert confirmed.status_code == 204

    item = next(i for i in updates.items() if i["step_title"] == "Clear liquids")

    assert item["step_done"] is True
    assert item["read"] is True
    assert item["urgency"] == "normal"


def test_a_care_team_message_can_be_read_and_marking_is_audited(
    updates: Updates, db_session: Session
) -> None:
    updates.staff_post(
        f"/appointments/{updates.booked.appointment.id}/messages",
        {"body": "Please bring your medicine list."},
    )

    [item] = updates.items()
    assert item["kind"] == "care_team_message"
    assert item["message"] == "Please bring your medicine list."
    assert item["read"] is False

    response = updates.read(item["key"])

    assert response.status_code == 200
    assert response.json() == {"unread_count": 0}
    assert updates.items()[0]["read"] is True
    assert updates.read(item["key"]).status_code == 200  # Marking twice is harmless.
    marks = db_session.scalars(
        select(AuditLog).where(
            AuditLog.patient_id == updates.booked.patient.id,
            AuditLog.purpose == "patient_notifications_read",
        )
    ).all()
    assert [m.action for m in marks] == [AuditAction.UPDATE, AuditAction.UPDATE]


def test_a_patient_cannot_mark_items_outside_their_own_feed(
    client: TestClient, settings: Settings, build: Builder, db_session: Session
) -> None:
    mine = Updates(client, settings, build, db_session)
    theirs = Updates(client, settings, build, db_session)
    theirs.staff_post(
        f"/appointments/{theirs.booked.appointment.id}/messages", {"body": "Hello from us."}
    )
    [their_item] = theirs.items()

    assert mine.read(their_item["key"]).status_code == 404
    assert mine.read("step-due:not-a-real-item").status_code == 404
    assert mine.items() == []
    assert theirs.items()[0]["read"] is False


def test_a_reschedule_request_shows_pending_then_the_answer_once(
    updates: Updates, db_session: Session
) -> None:
    requested = updates.client.post(
        f"/patient/appointments/{updates.booked.appointment.id}/reschedule-request",
        json={"note": None},
        headers=updates.headers,
    )
    assert requested.status_code == 204
    [pending] = updates.items()
    assert (pending["kind"], pending["request_status"], pending["urgency"]) == (
        "reschedule_request",
        "pending",
        "normal",
    )

    task = db_session.scalars(select(Task).where(Task.type == TaskType.RESCHEDULE)).one()
    new_time = dt.datetime.now(dt.UTC).replace(microsecond=0) + dt.timedelta(days=20)
    updates.staff_post(f"/requests/{task.id}/approve", {"scheduled_at": new_time.isoformat()})

    [approved] = updates.items()  # No separate "moved" item for the same change.
    assert approved["request_status"] == "approved"
    assert approved["urgency"] == "urgent"
    assert dt.datetime.fromisoformat(approved["scheduled_at"]) == new_time
    assert approved["key"] != pending["key"]


def test_a_declined_request_is_urgent(updates: Updates, db_session: Session) -> None:
    updates.client.post(
        f"/patient/appointments/{updates.booked.appointment.id}/reschedule-request",
        json={},
        headers=updates.headers,
    )
    task = db_session.scalars(select(Task).where(Task.type == TaskType.RESCHEDULE)).one()
    updates.staff_post(f"/requests/{task.id}/decline")

    [declined] = updates.items()

    assert (declined["request_status"], declined["urgency"]) == ("declined", "urgent")
    assert declined["scheduled_at"] is None


def test_staff_moving_or_cancelling_the_procedure_is_an_urgent_update(updates: Updates) -> None:
    appointment_id = updates.booked.appointment.id
    new_time = dt.datetime.now(dt.UTC).replace(microsecond=0) + dt.timedelta(days=15)
    updates.staff_post(
        f"/appointments/{appointment_id}/reschedule", {"scheduled_at": new_time.isoformat()}
    )

    [moved] = updates.items()
    assert (moved["kind"], moved["urgency"]) == ("appointment_moved", "urgent")
    assert dt.datetime.fromisoformat(moved["scheduled_at"]) == new_time

    updates.staff_post(f"/appointments/{appointment_id}/cancel", {"reason": "NO_ESCORT"})

    [cancelled] = updates.items()  # A cancelled procedure no longer shows its steps or moves.
    assert (cancelled["kind"], cancelled["urgency"]) == ("appointment_cancelled", "urgent")
    assert cancelled["key"] == f"cancelled:{appointment_id}"


def test_mark_all_read_clears_the_unread_count(updates: Updates, set_now: Clock) -> None:
    set_now(started(updates, "Clear liquids"))
    assert updates.feed()["unread_count"] == 3

    response = updates.client.post("/patient/notifications/read-all", headers=updates.headers)

    assert response.status_code == 200
    assert response.json() == {"unread_count": 0}
    assert updates.feed()["unread_count"] == 0


def test_staff_tokens_cannot_read_a_patient_feed(updates: Updates) -> None:
    response = updates.client.get("/patient/notifications", headers=updates.staff)

    assert response.status_code in (401, 403)


def test_the_portal_knows_the_hospital_name(updates: Updates, db_session: Session) -> None:
    org = db_session.get(Organization, updates.booked.patient.organization_id)
    assert org is not None

    me = updates.client.get("/patient/me", headers=updates.headers).json()

    assert me["hospital_name"] == org.name
