"""Staff notifications: newest first, rule-based urgency, per-person read marks, audited.

Also the newest-first order of the nurse inbox and the Requests page, and the Overview's flag
for a patient with an unread urgent item.
"""

import datetime as dt
from collections.abc import Callable
from typing import Any

import pytest
from api_testkit import Builder, patient_headers, staff_headers
from fastapi import FastAPI
from fastapi.testclient import TestClient
from messaging_testkit import Booked, book
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from prefix_api.api.deps import utcnow
from prefix_api.core.config import Settings
from prefix_api.db.models import AuditLog, Organization, StaffNotification, Task
from prefix_api.domain.enums import (
    AuditAction,
    EscalationSeverity,
    EscalationSource,
    Role,
    TaskStatus,
    TaskType,
)
from prefix_api.domain.principal import SystemPrincipal
from prefix_api.domain.urgency import PROCEDURE_SOON, UrgentReason, urgent_reasons
from prefix_api.services.check_ins import create_escalation

Clock = Callable[[dt.datetime], None]
T0 = dt.datetime(2026, 10, 30, 7, 30, tzinfo=dt.UTC)


@pytest.fixture
def set_now(app: FastAPI) -> Clock:
    def set_to(at: dt.datetime) -> None:
        app.dependency_overrides[utcnow] = lambda: at

    return set_to


class Ward:
    """One booked patient, their portal session and a coordinator in the same hospital."""

    def __init__(
        self,
        client: TestClient,
        settings: Settings,
        build: Builder,
        session: Session,
        days_ahead: int = 10,
    ) -> None:
        self.client = client
        self.settings = settings
        self.build = build
        self.booked: Booked = book(build, session, days_ahead=days_ahead)
        self.patient = patient_headers(settings, self.booked.patient)
        org = session.get(Organization, self.booked.patient.organization_id)
        assert org is not None
        self.org = org
        self.staff = self.colleague(Role.COORDINATOR)

    def colleague(self, role: Role) -> dict[str, str]:
        return staff_headers(self.settings, self.build.user(self.org, role))

    def raise_problem(self, step: str, note: str | None = None) -> None:
        event_id = self.booked.events[step].id
        response = self.client.post(
            f"/patient/steps/{event_id}/problem",
            json={"note": note} if note else {},
            headers=self.patient,
        )
        assert response.status_code == 204, response.text

    def feed(self, headers: dict[str, str] | None = None, **params: Any) -> dict[str, Any]:
        response = self.client.get("/notifications", params=params, headers=headers or self.staff)
        assert response.status_code == 200, response.text
        result: dict[str, Any] = response.json()
        return result

    def items(self, **params: Any) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = self.feed(**params)["items"]
        return items


@pytest.fixture
def ward(client: TestClient, settings: Settings, build: Builder, db_session: Session) -> Ward:
    return Ward(client, settings, build, db_session)


def at(ward: Ward, minutes: int) -> dt.datetime:
    """A moment while every step can still be reported (well before the procedure)."""
    start = ward.booked.appointment.scheduled_at - dt.timedelta(days=5)
    return start + dt.timedelta(minutes=minutes)


# -- order ---------------------------------------------------------------------------------


def test_two_problems_raised_two_minutes_apart_list_the_newer_first(
    ward: Ward, set_now: Clock
) -> None:
    set_now(at(ward, 0))
    ward.raise_problem("Low-fibre diet")
    set_now(at(ward, 2))
    ward.raise_problem("Arrange escort")

    items = ward.items()

    assert [i["summary"] for i in items] == [
        "Cannot complete: Arrange escort",
        "Cannot complete: Low-fibre diet",
    ]
    assert [dt.datetime.fromisoformat(i["created_at"]) for i in items] == [
        at(ward, 2),
        at(ward, 0),
    ]


def test_an_urgent_item_does_not_jump_ahead_of_a_newer_one(ward: Ward, set_now: Clock) -> None:
    set_now(at(ward, 0))
    ward.raise_problem("Clear liquids")  # critical, so urgent
    set_now(at(ward, 2))
    ward.raise_problem("Arrange escort")

    items = ward.items()

    assert [(i["summary"], i["urgent"]) for i in items] == [
        ("Cannot complete: Arrange escort", False),
        ("Cannot complete: Clear liquids", True),
    ]


def test_items_raised_at_the_same_moment_fall_back_to_the_id(
    ward: Ward, set_now: Clock, db_session: Session
) -> None:
    set_now(at(ward, 0))
    ward.raise_problem("Low-fibre diet")
    ward.raise_problem("Arrange escort")
    ids = db_session.scalars(
        select(StaffNotification.id).where(StaffNotification.patient_id == ward.booked.patient.id)
    ).all()

    assert [i["id"] for i in ward.items()] == [str(i) for i in sorted(ids, reverse=True)]


def test_each_item_says_who_what_and_when(ward: Ward, set_now: Clock) -> None:
    set_now(at(ward, 0))
    ward.raise_problem("Arrange escort", note="My son is away that day")

    [item] = ward.items()

    patient = ward.booked.patient
    assert item["kind"] == "PROBLEM"
    assert item["patient_name"] == f"{patient.first_name} {patient.last_name}"
    assert item["patient_id"] == str(patient.id)
    assert item["appointment_id"] == str(ward.booked.appointment.id)
    assert item["procedure_name"] == "Colonoscopy"
    # A fixed template: the patient's own words stay in the encrypted records behind it.
    assert item["summary"] == "Cannot complete: Arrange escort"
    assert item["timezone"] == "Asia/Kolkata"
    assert item["read"] is False
    assert item["open"] is True


# -- severity --------------------------------------------------------------------------------


def test_the_urgency_rules() -> None:
    def procedure_in(gap: dt.timedelta | None) -> tuple[UrgentReason, ...]:
        scheduled_at = None if gap is None else T0 + gap
        return urgent_reasons(
            red_flag=False, critical_step=False, scheduled_at=scheduled_at, now=T0
        )

    minute = dt.timedelta(minutes=1)
    assert procedure_in(dt.timedelta(days=3)) == ()
    assert procedure_in(None) == ()
    assert procedure_in(PROCEDURE_SOON) == (UrgentReason.PROCEDURE_SOON,)
    assert procedure_in(PROCEDURE_SOON + minute) == ()
    # A procedure that has already started is not "within the next 24 hours".
    assert procedure_in(-minute) == ()
    assert urgent_reasons(
        red_flag=True, critical_step=True, scheduled_at=T0 + dt.timedelta(hours=2), now=T0
    ) == (UrgentReason.RED_FLAG, UrgentReason.CRITICAL_STEP, UrgentReason.PROCEDURE_SOON)


def test_a_problem_with_an_ordinary_step_days_ahead_is_not_urgent(
    ward: Ward, set_now: Clock
) -> None:
    set_now(at(ward, 0))
    ward.raise_problem("Arrange escort")

    [item] = ward.items()

    assert item["urgent"] is False
    assert item["urgent_reasons"] == []


def test_a_problem_with_a_critical_step_is_urgent(ward: Ward, set_now: Clock) -> None:
    set_now(at(ward, 0))
    ward.raise_problem("Clear liquids")

    [item] = ward.items()

    assert item["urgent"] is True
    assert item["urgent_reasons"] == ["critical_step"]


def test_red_flag_words_in_the_note_make_it_urgent(ward: Ward, set_now: Clock) -> None:
    set_now(at(ward, 0))
    ward.raise_problem("Arrange escort", note="I have chest pain since this morning")

    [item] = ward.items()

    assert item["urgent_reasons"] == ["red_flag"]
    assert item["summary"] == "Cannot complete: Arrange escort. Mentions chest pain"


def test_a_problem_within_a_day_of_the_procedure_is_urgent(ward: Ward, set_now: Clock) -> None:
    set_now(ward.booked.appointment.scheduled_at - dt.timedelta(hours=12))
    ward.raise_problem("Arrange escort")

    [item] = ward.items()

    assert item["urgent_reasons"] == ["procedure_soon"]


def test_urgent_only_keeps_the_order_and_counts_urgent_items(ward: Ward, set_now: Clock) -> None:
    set_now(at(ward, 0))
    ward.raise_problem("Clear liquids")
    set_now(at(ward, 1))
    ward.raise_problem("Arrange escort", note="chest pain")
    set_now(at(ward, 2))
    ward.raise_problem("Low-fibre diet")

    feed = ward.feed(urgent_only="true")

    assert [i["summary"] for i in feed["items"]] == [
        "Cannot complete: Arrange escort. Mentions chest pain",
        "Cannot complete: Clear liquids",
    ]
    assert (feed["unread_count"], feed["urgent_count"]) == (3, 2)


# -- read and unread ---------------------------------------------------------------------


def test_marking_an_item_read_is_per_person_and_audited(
    ward: Ward, set_now: Clock, db_session: Session
) -> None:
    set_now(at(ward, 0))
    ward.raise_problem("Clear liquids")
    [item] = ward.items()
    nurse = ward.colleague(Role.NURSE)

    response = ward.client.post(
        "/notifications/read", json={"ids": [item["id"]]}, headers=ward.staff
    )

    assert response.status_code == 200
    assert response.json() == {"latest_id": item["id"], "unread_count": 0, "urgent_count": 0}
    assert ward.items()[0]["read"] is True
    # The nurse has not opened it yet.
    nurse_feed = ward.feed(headers=nurse)
    assert nurse_feed["items"][0]["read"] is False
    assert (nurse_feed["unread_count"], nurse_feed["urgent_count"]) == (1, 1)
    marks = db_session.scalars(
        select(AuditLog).where(
            AuditLog.entity_type == "staff_notification",
            AuditLog.action == AuditAction.UPDATE,
        )
    ).all()
    assert [(m.patient_id, m.purpose) for m in marks] == [
        (ward.booked.patient.id, "staff_notifications_read")
    ]


def test_mark_all_read_clears_the_counts(ward: Ward, set_now: Clock) -> None:
    set_now(at(ward, 0))
    ward.raise_problem("Clear liquids")
    ward.raise_problem("Arrange escort")

    response = ward.client.post("/notifications/read-all", headers=ward.staff)

    assert response.json()["unread_count"] == 0
    assert all(i["read"] for i in ward.items())


def test_an_item_whose_task_is_done_counts_as_read(
    ward: Ward, set_now: Clock, db_session: Session
) -> None:
    set_now(at(ward, 0))
    ward.raise_problem("Arrange escort")
    task = db_session.scalar(select(Task).where(Task.patient_id == ward.booked.patient.id))
    assert task is not None
    task.status = TaskStatus.DONE
    db_session.flush()

    [item] = ward.items()

    assert (item["open"], item["read"]) == (False, True)


def test_another_hospitals_item_cannot_be_marked(
    ward: Ward,
    set_now: Clock,
    client: TestClient,
    settings: Settings,
    build: Builder,
    db_session: Session,
) -> None:
    set_now(at(ward, 0))
    ward.raise_problem("Arrange escort")
    [item] = ward.items()
    other = Ward(client, settings, build, db_session)

    response = client.post("/notifications/read", json={"ids": [item["id"]]}, headers=other.staff)

    assert response.status_code == 404
    assert other.feed()["items"] == []


def test_reading_the_feed_is_audited_per_item(
    ward: Ward, set_now: Clock, db_session: Session
) -> None:
    set_now(at(ward, 0))
    ward.raise_problem("Arrange escort")

    [item] = ward.items()

    listed = db_session.scalars(
        select(AuditLog).where(
            AuditLog.entity_type == "staff_notification", AuditLog.action == AuditAction.LIST
        )
    ).all()
    assert [(str(a.entity_id), a.patient_id) for a in listed] == [
        (item["id"], ward.booked.patient.id)
    ]


def test_the_summary_the_bell_polls_holds_no_patient_data_and_is_not_audited(
    ward: Ward, set_now: Clock, db_session: Session
) -> None:
    def audit_rows() -> int:
        return db_session.scalar(select(func.count()).select_from(AuditLog)) or 0

    empty = ward.client.get("/notifications/summary", headers=ward.staff).json()
    set_now(at(ward, 0))
    ward.raise_problem("Clear liquids")
    before = audit_rows()

    summary = ward.client.get("/notifications/summary", headers=ward.staff).json()

    assert empty == {"latest_id": None, "unread_count": 0, "urgent_count": 0}
    assert set(summary) == {"latest_id", "unread_count", "urgent_count"}
    assert (summary["unread_count"], summary["urgent_count"]) == (1, 1)
    assert audit_rows() == before


def test_roles_without_patient_work_cannot_read_notifications(ward: Ward) -> None:
    viewer = ward.colleague(Role.VIEWER)

    assert ward.client.get("/notifications", headers=viewer).status_code == 403
    assert ward.client.get("/notifications/summary", headers=viewer).status_code == 403
    assert ward.client.get("/notifications", headers=ward.patient).status_code == 401


# -- where patients raise things -----------------------------------------------------------


def test_a_reschedule_request_is_a_notification(ward: Ward, set_now: Clock) -> None:
    set_now(at(ward, 0))
    response = ward.client.post(
        f"/patient/appointments/{ward.booked.appointment.id}/reschedule-request",
        json={"note": "I will be travelling"},
        headers=ward.patient,
    )
    assert response.status_code == 204

    [item] = ward.items()

    assert (item["kind"], item["summary"], item["urgent"]) == (
        "RESCHEDULE",
        "Asked to move the procedure",
        False,
    )


# -- the inbox, the Requests page and the Overview ---------------------------------------------


def test_the_inbox_lists_the_newest_first_and_marks_urgency_by_rule(
    ward: Ward, db_session: Session
) -> None:
    system = SystemPrincipal(organization_id=ward.org.id, job="test")
    older = create_escalation(
        db_session,
        principal=system,
        patient=ward.booked.patient,
        appointment=ward.booked.appointment,
        severity=EscalationSeverity.URGENT,
        summary="Chest pain",
        purpose="test",
        source=EscalationSource.RED_FLAG,
    )
    newer = create_escalation(
        db_session,
        principal=system,
        patient=ward.booked.patient,
        appointment=ward.booked.appointment,
        severity=EscalationSeverity.NORMAL,
        summary="A question",
        purpose="test",
        source=EscalationSource.OUT_OF_PROTOCOL,
    )
    older.created_at = T0
    newer.created_at = T0 + dt.timedelta(minutes=2)
    db_session.flush()

    rows = ward.client.get("/escalations", headers=ward.staff).json()

    assert [(r["id"], r["urgent"], r["urgent_reasons"]) for r in rows] == [
        (str(newer.id), False, []),
        (str(older.id), True, ["red_flag"]),
    ]
    assert rows[0]["timezone"] == "Asia/Kolkata"


def test_the_requests_page_lists_the_newest_first(ward: Ward, db_session: Session) -> None:
    def request(created_at: dt.datetime) -> Task:
        task = Task(
            organization_id=ward.org.id,
            type=TaskType.RESCHEDULE,
            title="Patient asked to reschedule",
            appointment_id=ward.booked.appointment.id,
            patient_id=ward.booked.patient.id,
            created_at=created_at,
        )
        db_session.add(task)
        return task

    older = request(T0)
    newer = request(T0 + dt.timedelta(minutes=2))
    db_session.flush()

    rows = ward.client.get("/requests", headers=ward.staff).json()

    assert [r["id"] for r in rows] == [str(newer.id), str(older.id)]
    assert rows[0]["timezone"] == "Asia/Kolkata"
    assert rows[0]["urgent"] is False


def test_the_overview_flags_a_patient_with_an_unread_urgent_item(
    client: TestClient, settings: Settings, build: Builder, db_session: Session
) -> None:
    near = Ward(client, settings, build, db_session, days_ahead=2)

    def flagged() -> bool:
        [row] = client.get("/dashboard/upcoming", headers=near.staff).json()
        result: bool = row["urgent_unread"]
        return result

    assert flagged() is False
    near.raise_problem("Clear liquids")
    assert flagged() is True

    [item] = near.items()
    client.post("/notifications/read", json={"ids": [item["id"]]}, headers=near.staff)

    assert flagged() is False
