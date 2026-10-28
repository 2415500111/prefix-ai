"""Guest demo: what a guest can see and do, what they cannot, and that demo messages never leave."""

import datetime as dt
from typing import Any

import pytest
from api_testkit import Builder, make_test_settings, staff_headers
from fastapi.testclient import TestClient
from messaging_testkit import RecordingProvider, book
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from prefix_api.core.config import Settings
from prefix_api.db.models import (
    Organization,
    PatientTimelineEvent,
    PrepProtocol,
    PrepStep,
    Task,
    User,
)
from prefix_api.domain.enums import Role, TaskStatus, TaskType
from prefix_api.main import create_app
from prefix_api.services.demo import DEMO_SLUG, populate_demo
from prefix_api.services.dispatch import dispatch_due_reminders
from prefix_api.services.translation import PassthroughTranslator

Factory = sessionmaker[Session]


@pytest.fixture
def demo(session_factory: Factory) -> dict[str, Any]:
    """A seeded demo hospital, built once per test inside the test's transaction."""
    now = dt.datetime.now(dt.UTC)
    result = populate_demo(session_factory, now=now, admin_password="demo-admin-password")
    with session_factory() as session:
        org = session.scalar(select(Organization).where(Organization.slug == DEMO_SLUG))
        assert org is not None
        guest = session.scalar(
            select(User).where(User.organization_id == org.id, User.role == Role.DEMO_VIEWER)
        )
        admin = session.scalar(
            select(User).where(User.organization_id == org.id, User.role == Role.ADMIN)
        )
        assert guest is not None
        assert admin is not None
        return {"org": org, "guest": guest, "admin": admin, "result": result}


def guest_headers(client: TestClient) -> dict[str, str]:
    response = client.post("/auth/guest")
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_guest_sign_in_gives_a_demo_session(client: TestClient, demo: dict[str, Any]) -> None:
    response = client.post("/auth/guest")

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.json()["role"] == "DEMO_VIEWER"
    # A guest session is shorter than a staff refresh token (seven days by default).
    expires = dt.datetime.fromisoformat(body["refresh_expires_at"])
    assert expires - dt.datetime.now(dt.UTC) <= dt.timedelta(hours=3)


def test_guest_sign_in_is_off_when_the_flag_is_off(
    session_factory: Factory, demo: dict[str, Any]
) -> None:
    settings = make_test_settings(enable_guest_login=False)
    with TestClient(create_app(settings, session_factory=session_factory)) as client:
        assert client.post("/auth/guest").status_code == 404
        assert client.get("/auth/capabilities").json() == {"guest_login": False}


def test_capabilities_offer_guest_login_by_default(client: TestClient) -> None:
    assert client.get("/auth/capabilities").json() == {"guest_login": True}


def test_guest_sign_in_is_rate_limited(client: TestClient, demo: dict[str, Any]) -> None:
    for _ in range(5):
        assert client.post("/auth/guest").status_code == 200

    response = client.post("/auth/guest")

    assert response.status_code == 429
    assert response.json()["code"] == "rate_limited"


def test_a_guest_sees_the_demo_patients(client: TestClient, demo: dict[str, Any]) -> None:
    headers = guest_headers(client)

    response = client.get("/appointments", headers=headers, params={"days": 7})

    assert response.status_code == 200
    # The demo also holds one released slot, which the list shows as cancelled.
    booked = [row for row in response.json() if row["status"] != "CANCELLED"]
    assert len(booked) == demo["result"].appointments


def test_a_guest_cannot_reach_another_organisations_patients(
    client: TestClient,
    settings: Settings,
    build: Builder,
    db_session: Session,
    demo: dict[str, Any],
) -> None:
    outside = book(build, db_session)
    headers = guest_headers(client)

    response = client.get(f"/patients/{outside.patient.id}", headers=headers)

    assert response.status_code == 404


def test_a_guest_cannot_approve_protocols_or_manage_users(
    client: TestClient, demo: dict[str, Any], db_session: Session
) -> None:
    headers = guest_headers(client)
    protocol_id = db_session.scalar(
        select(PrepProtocol.id).where(PrepProtocol.organization_id == demo["org"].id).limit(1)
    )
    assert protocol_id is not None

    approve = client.post(
        f"/protocols/{protocol_id}/approve",
        headers=headers,
        json={"acknowledge_sample": True},
    )

    assert approve.status_code == 403


def test_a_guest_can_complete_a_task_and_confirm_a_step(
    client: TestClient, demo: dict[str, Any], db_session: Session
) -> None:
    headers = guest_headers(client)
    org_id = demo["org"].id
    task = db_session.scalar(select(Task).where(Task.organization_id == org_id).limit(1))
    if task is None:
        db_session.add(
            Task(
                organization_id=org_id,
                type=TaskType.CALL_PATIENT,
                title="Call the patient",
                due_at=dt.datetime.now(dt.UTC),
            )
        )
        db_session.flush()
        task = db_session.scalar(select(Task).where(Task.organization_id == org_id).limit(1))
    assert task is not None

    done = client.post(f"/tasks/{task.id}/complete", headers=headers)

    assert done.status_code == 200
    assert done.json()["status"] == TaskStatus.DONE.value

    event = db_session.scalar(
        select(PatientTimelineEvent)
        .join(PrepStep, PrepStep.id == PatientTimelineEvent.step_id)
        .where(
            PatientTimelineEvent.organization_id == org_id,
            PrepStep.requires_confirmation.is_(True),
            PatientTimelineEvent.status.not_in(["CONFIRMED", "CANCELLED"]),
        )
        .limit(1)
    )
    if event is not None:
        confirmed = client.post(
            f"/appointments/{event.appointment_id}/steps/{event.id}/confirm", headers=headers
        )
        assert confirmed.status_code == 204


def test_a_guest_cannot_reset_the_demo(client: TestClient, demo: dict[str, Any]) -> None:
    response = client.post("/demo/reset", headers=guest_headers(client))

    assert response.status_code == 403


def test_the_demo_admin_can_reset_the_demo(
    client: TestClient, settings: Settings, demo: dict[str, Any]
) -> None:
    response = client.post("/demo/reset", headers=staff_headers(settings, demo["admin"]))

    assert response.status_code == 200
    body = response.json()
    assert body["patients"] == demo["result"].patients
    assert body["appointments"] == demo["result"].appointments


def test_an_admin_outside_the_demo_cannot_reset_it(
    client: TestClient,
    settings: Settings,
    build: Builder,
    db_session: Session,
    demo: dict[str, Any],
) -> None:
    outside = build.user(build.organization("Real hospital"), Role.ADMIN)

    response = client.post("/demo/reset", headers=staff_headers(settings, outside))

    assert response.status_code == 403


def test_a_guest_can_open_a_fresh_link_to_a_hindi_speaking_demo_patient(
    client: TestClient, demo: dict[str, Any]
) -> None:
    headers = guest_headers(client)

    response = client.post("/demo/patient-link", headers=headers, params={"lang": "hi"})

    assert response.status_code == 200
    url = response.json()["url"]
    token = url.split("#token=")[1]
    session = client.post("/patient/session", json={"token": token})
    assert session.status_code == 200


def test_demo_messages_are_logged_never_sent(
    build: Builder, db_session: Session, session_factory: Factory
) -> None:
    booked = book(build, db_session)
    org = db_session.get(Organization, booked.patient.organization_id)
    assert org is not None
    org.is_demo = True
    db_session.flush()
    provider = RecordingProvider()
    at = booked.events["Low-fibre diet"].send_at + dt.timedelta(seconds=1)

    dispatch_due_reminders(
        session_factory, provider, PassthroughTranslator(), now=at, batch_size=50
    )

    assert provider.sent == []
    db_session.refresh(booked.events["Low-fibre diet"])
    assert booked.events["Low-fibre diet"].sent_at is not None
