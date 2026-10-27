"""Appointments and the prep timeline built from approved protocols."""

import datetime as dt
import uuid
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from api_testkit import Builder, StepSpec, staff_headers
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from prefix_api.core.config import Settings
from prefix_api.db.models import (
    AuditLog,
    CheckIn,
    Organization,
    Patient,
    PatientTimelineEvent,
    PrepProtocol,
    PrepStep,
    ProcedureType,
)
from prefix_api.domain.enums import (
    AuditAction,
    CheckInStatus,
    ProtocolStatus,
    Role,
    TimelineEventStatus,
)

KOLKATA = ZoneInfo("Asia/Kolkata")
DAY = 24 * 60
STEPS = [
    StepSpec(7 * DAY, "Blood thinner", is_critical=True, conditions={"flag": "on_anticoagulant"}),
    StepSpec(3 * DAY, "Low-fibre diet"),
    StepSpec(6 * 60, "Second prep dose", is_critical=True, requires_confirmation=True),
    StepSpec(10 * 60, "Late evening reminder"),
]


class World:
    def __init__(self, build: Builder, settings: Settings) -> None:
        self.build = build
        self.org: Organization = build.organization()
        self.facility = build.facility(self.org, timezone="Asia/Kolkata")
        self.procedure: ProcedureType = build.procedure_type(self.org)
        self.protocol: PrepProtocol = build.approved_protocol(self.org, self.procedure, STEPS)
        self.patient: Patient = build.patient(self.org)
        self.coordinator = staff_headers(settings, build.user(self.org, Role.COORDINATOR))

    def booking(self, scheduled: dt.datetime, **overrides: Any) -> dict[str, Any]:
        return {
            "patient_id": str(self.patient.id),
            "facility_id": str(self.facility.id),
            "procedure_type_id": str(self.procedure.id),
            "scheduled_at": scheduled.isoformat(),
            **overrides,
        }


@pytest.fixture
def world(build: Builder, settings: Settings) -> World:
    return World(build, settings)


def in_days(days: int, hour: int = 9) -> dt.datetime:
    day = (dt.datetime.now(KOLKATA) + dt.timedelta(days=days)).date()
    return dt.datetime.combine(day, dt.time(hour, 0), tzinfo=KOLKATA)


def book(
    client: TestClient, world: World, scheduled: dt.datetime, **overrides: Any
) -> dict[str, Any]:
    response = client.post(
        "/appointments", json=world.booking(scheduled, **overrides), headers=world.coordinator
    )
    assert response.status_code == 201, response.text
    created: dict[str, Any] = response.json()
    return created


def timeline(client: TestClient, world: World, appointment_id: str) -> list[dict[str, Any]]:
    response = client.get(f"/appointments/{appointment_id}", headers=world.coordinator)
    assert response.status_code == 200, response.text
    events: list[dict[str, Any]] = response.json()["timeline"]
    return events


def local(value: str) -> str:
    return dt.datetime.fromisoformat(value).astimezone(KOLKATA).strftime("%Y-%m-%d %H:%M")


def test_booking_builds_the_timeline_from_applicable_steps(
    client: TestClient, world: World
) -> None:
    scheduled = in_days(10)
    appointment = book(client, world, scheduled)

    events = {e["title"]: e for e in timeline(client, world, appointment["id"])}

    # The blood-thinner step only applies to patients on an anticoagulant.
    assert set(events) == {"Low-fibre diet", "Second prep dose", "Late evening reminder"}
    assert appointment["protocol_id"] == str(world.protocol.id)
    assert all(e["status"] == "PENDING" for e in events.values())
    day_before = (scheduled - dt.timedelta(days=1)).strftime("%Y-%m-%d")
    procedure_day = scheduled.strftime("%Y-%m-%d")
    # 3 days before at the same clock time.
    assert local(events["Low-fibre diet"]["due_at"]) == (scheduled - dt.timedelta(days=3)).strftime(
        "%Y-%m-%d 09:00"
    )
    # Critical step due at 03:00 keeps its time; non-critical 23:00 moves to 21:30.
    assert local(events["Second prep dose"]["send_at"]) == f"{procedure_day} 03:00"
    assert local(events["Late evening reminder"]["due_at"]) == f"{day_before} 23:00"
    assert local(events["Late evening reminder"]["send_at"]) == f"{day_before} 21:30"


def test_condition_flags_include_extra_steps(
    client: TestClient, world: World, db_session: Session
) -> None:
    world.patient.on_anticoagulant = True
    db_session.flush()

    titles = {e["title"] for e in timeline(client, world, book(client, world, in_days(10))["id"])}

    assert "Blood thinner" in titles


def test_late_booking_sends_missed_critical_steps_now(
    client: TestClient, world: World, db_session: Session
) -> None:
    world.patient.on_anticoagulant = True
    db_session.flush()
    before = dt.datetime.now(dt.UTC)

    events = {e["title"]: e for e in timeline(client, world, book(client, world, in_days(2))["id"])}

    blood_thinner = events["Blood thinner"]
    assert dt.datetime.fromisoformat(blood_thinner["due_at"]) < before
    assert dt.datetime.fromisoformat(blood_thinner["send_at"]) >= before
    assert blood_thinner["status"] == "PENDING"


def test_booking_requires_an_approved_protocol(
    client: TestClient, world: World, build: Builder
) -> None:
    other_procedure = build.procedure_type(world.org, code="MRI")

    response = client.post(
        "/appointments",
        json=world.booking(in_days(5), procedure_type_id=str(other_procedure.id)),
        headers=world.coordinator,
    )

    assert response.status_code == 422
    assert "approved protocol" in response.json()["detail"]


def test_several_approved_protocols_need_an_explicit_choice(
    client: TestClient, world: World, build: Builder
) -> None:
    second = build.approved_protocol(world.org, world.procedure, STEPS[1:2], name="Variant")

    ambiguous = client.post(
        "/appointments", json=world.booking(in_days(5)), headers=world.coordinator
    )
    chosen = book(client, world, in_days(5), protocol_id=str(second.id))

    assert ambiguous.status_code == 422
    assert chosen["protocol_id"] == str(second.id)


def test_a_draft_protocol_can_never_be_booked(
    client: TestClient, world: World, db_session: Session
) -> None:
    draft = PrepProtocol(
        organization_id=world.org.id,
        family_id=uuid.uuid7(),
        version=1,
        procedure_type_id=world.procedure.id,
        name="Draft",
    )
    db_session.add(draft)
    db_session.flush()

    response = client.post(
        "/appointments",
        json=world.booking(in_days(5), protocol_id=str(draft.id)),
        headers=world.coordinator,
    )

    assert response.status_code == 422


def test_past_dates_are_rejected(client: TestClient, world: World) -> None:
    response = client.post(
        "/appointments", json=world.booking(in_days(-1)), headers=world.coordinator
    )

    assert response.status_code == 422


def test_reschedule_replaces_the_timeline(
    client: TestClient, world: World, db_session: Session
) -> None:
    appointment = book(client, world, in_days(10))
    first = timeline(client, world, appointment["id"])
    pending_check_in = CheckIn(
        organization_id=world.org.id,
        appointment_id=uuid.UUID(appointment["id"]),
        patient_id=world.patient.id,
        timeline_event_id=uuid.UUID(first[0]["id"]),
        question="Done?",
    )
    db_session.add(pending_check_in)
    db_session.flush()

    response = client.post(
        f"/appointments/{appointment['id']}/reschedule",
        json={"scheduled_at": in_days(20).isoformat()},
        headers=world.coordinator,
    )
    second = timeline(client, world, appointment["id"])

    assert response.status_code == 200
    old_ids = {e["id"] for e in first}
    assert all(e["status"] == "CANCELLED" for e in second if e["id"] in old_ids)
    active = [e for e in second if e["id"] not in old_ids]
    assert {e["title"] for e in active} == {e["title"] for e in first}
    assert all(e["status"] == "PENDING" for e in active)
    db_session.refresh(pending_check_in)
    assert pending_check_in.status is CheckInStatus.EXPIRED


def test_reschedule_uses_the_newest_approved_version(
    client: TestClient, world: World, build: Builder, db_session: Session
) -> None:
    appointment = book(client, world, in_days(10))
    revised = PrepProtocol(
        organization_id=world.org.id,
        family_id=world.protocol.family_id,
        version=2,
        procedure_type_id=world.procedure.id,
        name="Prep v2",
    )
    db_session.add(revised)
    db_session.flush()
    revised.steps.append(
        PrepStep(
            organization_id=world.org.id,
            offset_minutes=DAY,
            title="New step",
            instruction_text="New.",
            category=world.protocol.steps[0].category,
        )
    )
    db_session.flush()
    world.protocol.status = ProtocolStatus.RETIRED
    revised.status = ProtocolStatus.APPROVED
    revised.approved_by_id = world.protocol.approved_by_id
    revised.approved_at = dt.datetime.now(dt.UTC)
    db_session.flush()

    moved = client.post(
        f"/appointments/{appointment['id']}/reschedule",
        json={"scheduled_at": in_days(12).isoformat()},
        headers=world.coordinator,
    ).json()

    assert moved["protocol_id"] == str(revised.id)
    active = [e for e in timeline(client, world, appointment["id"]) if e["status"] != "CANCELLED"]
    assert [e["title"] for e in active] == ["New step"]


def test_cancel_stops_all_reminders(client: TestClient, world: World) -> None:
    appointment = book(client, world, in_days(10))

    response = client.post(
        f"/appointments/{appointment['id']}/cancel",
        json={"reason": "PATIENT_REQUESTED", "note": "Travelling"},
        headers=world.coordinator,
    )
    again = client.post(
        f"/appointments/{appointment['id']}/cancel",
        json={"reason": "OTHER"},
        headers=world.coordinator,
    )
    move = client.post(
        f"/appointments/{appointment['id']}/reschedule",
        json={"scheduled_at": in_days(12).isoformat()},
        headers=world.coordinator,
    )

    assert response.json()["status"] == "CANCELLED"
    assert response.json()["cancellation_reason"] == "PATIENT_REQUESTED"
    assert all(e["status"] == "CANCELLED" for e in timeline(client, world, appointment["id"]))
    assert again.status_code == 409
    assert move.status_code == 409


def test_appointment_changes_are_audited(
    client: TestClient, world: World, db_session: Session
) -> None:
    appointment = book(client, world, in_days(10))
    client.post(
        f"/appointments/{appointment['id']}/cancel",
        json={"reason": "OTHER"},
        headers=world.coordinator,
    )

    rows = db_session.scalars(
        select(AuditLog)
        .where(AuditLog.entity_id == uuid.UUID(appointment["id"]))
        .order_by(AuditLog.id)
    ).all()

    assert [r.action for r in rows] == [AuditAction.CREATE, AuditAction.UPDATE]
    assert all(r.patient_id == world.patient.id for r in rows)


def test_nurses_cannot_book(
    client: TestClient, world: World, build: Builder, settings: Settings
) -> None:
    nurse = staff_headers(settings, build.user(world.org, Role.NURSE))

    assert (
        client.post("/appointments", json=world.booking(in_days(5)), headers=nurse).status_code
        == 403
    )


def test_appointments_are_tenant_scoped(
    client: TestClient, world: World, build: Builder, settings: Settings
) -> None:
    appointment = book(client, world, in_days(5))
    outsider = staff_headers(settings, build.user(build.organization(), Role.ADMIN))

    assert client.get(f"/appointments/{appointment['id']}", headers=outsider).status_code == 404
    other_patient_booking = world.booking(in_days(5))
    assert (
        client.post("/appointments", json=other_patient_booking, headers=outsider).status_code
        == 422
    )


def test_upcoming_list(client: TestClient, world: World) -> None:
    soon = book(client, world, in_days(1))
    later = book(client, world, in_days(9))

    listed = client.get("/appointments?days=3", headers=world.coordinator).json()

    assert [a["id"] for a in listed] == [soon["id"]]
    assert later["id"] not in {a["id"] for a in listed}


def test_events_use_the_facility_timezone(
    client: TestClient, world: World, build: Builder, db_session: Session
) -> None:
    ny = build.facility(world.org, timezone="America/New_York")
    scheduled = dt.datetime.now(ZoneInfo("America/New_York")).replace(
        hour=9, minute=0, second=0, microsecond=0
    ) + dt.timedelta(days=10)

    appointment = book(client, world, scheduled, facility_id=str(ny.id))
    events = db_session.scalars(
        select(PatientTimelineEvent).where(
            PatientTimelineEvent.appointment_id == uuid.UUID(appointment["id"])
        )
    ).all()
    late = next(
        e
        for e in events
        if e.status is TimelineEventStatus.PENDING
        and e.due_at.astimezone(ZoneInfo("America/New_York")).hour == 23
    )

    assert late.send_at.astimezone(ZoneInfo("America/New_York")).strftime("%H:%M") == "21:30"
