"""Staff workflows behind the redesigned patient sheet: calls, messages, reschedule requests and
sidebar badges."""

import datetime as dt

from api_testkit import Builder, staff_headers
from fastapi.testclient import TestClient
from messaging_testkit import Booked, book
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from prefix_api.core.config import Settings
from prefix_api.db.models import Appointment, AuditLog, Escalation, Organization, Task
from prefix_api.domain.enums import (
    EscalationSeverity,
    EscalationSource,
    EscalationStatus,
    Role,
    TaskStatus,
    TaskType,
)


def headers_for(
    build: Builder, session: Session, booked: Booked, settings: Settings, role: Role
) -> dict[str, str]:
    org = session.get(Organization, booked.patient.organization_id)
    assert org is not None
    return staff_headers(settings, build.user(org, role))


def open_task(session: Session, booked: Booked, task_type: TaskType) -> Task:
    task = Task(
        organization_id=booked.patient.organization_id,
        type=task_type,
        title="Patient asked to reschedule" if task_type is TaskType.RESCHEDULE else "Call",
        status=TaskStatus.OPEN,
        appointment_id=booked.appointment.id,
        patient_id=booked.patient.id,
    )
    session.add(task)
    session.flush()
    return task


def test_logging_a_call_closes_the_open_call_tasks_and_is_audited(
    client: TestClient, build: Builder, db_session: Session, settings: Settings
) -> None:
    booked = book(build, db_session)
    headers = headers_for(build, db_session, booked, settings, Role.COORDINATOR)
    pending = open_task(db_session, booked, TaskType.CALL_PATIENT)

    response = client.post(f"/appointments/{booked.appointment.id}/calls", headers=headers)

    assert response.status_code == 201
    assert response.json()["status"] == "DONE"
    db_session.refresh(pending)
    assert pending.status is TaskStatus.DONE
    assert pending.completed_at is not None
    audit = db_session.scalars(
        select(AuditLog).where(AuditLog.purpose == "care_team_contact")
    ).all()
    assert {row.action for row in audit} == {"UPDATE", "CREATE"}
    assert all(row.patient_id == booked.patient.id for row in audit)


def test_a_guest_can_log_a_call_but_cannot_message_a_patient(
    client: TestClient, build: Builder, db_session: Session, settings: Settings
) -> None:
    booked = book(build, db_session)
    guest = headers_for(build, db_session, booked, settings, Role.DEMO_VIEWER)

    call = client.post(f"/appointments/{booked.appointment.id}/calls", headers=guest)
    message = client.post(
        f"/appointments/{booked.appointment.id}/messages",
        json={"body": "Please call us back."},
        headers=guest,
    )

    assert call.status_code == 201
    assert message.status_code == 403


def test_a_staff_message_is_encrypted_and_shown_in_the_patient_sheet(
    client: TestClient, build: Builder, db_session: Session, settings: Settings
) -> None:
    booked = book(build, db_session)
    headers = headers_for(build, db_session, booked, settings, Role.NURSE)
    body = "Please bring your medicine list on the day."

    sent = client.post(
        f"/appointments/{booked.appointment.id}/messages", json={"body": body}, headers=headers
    )

    assert sent.status_code == 201
    stored = db_session.execute(
        text("SELECT body FROM message WHERE id = :id"), {"id": sent.json()["id"]}
    ).scalar_one()
    assert body not in str(stored)

    coordinator = headers_for(build, db_session, booked, settings, Role.COORDINATOR)
    drawer = client.get(
        f"/dashboard/appointments/{booked.appointment.id}", headers=coordinator
    ).json()
    staff_messages = [m for m in drawer["messages"] if m["provider"] == "care_team"]
    assert [m["body"] for m in staff_messages] == [body]
    assert staff_messages[0]["direction"] == "OUTBOUND"


def test_an_empty_message_is_refused(
    client: TestClient, build: Builder, db_session: Session, settings: Settings
) -> None:
    booked = book(build, db_session)
    headers = headers_for(build, db_session, booked, settings, Role.COORDINATOR)

    response = client.post(
        f"/appointments/{booked.appointment.id}/messages", json={"body": "   "}, headers=headers
    )

    assert response.status_code == 422


def test_approving_a_request_moves_the_procedure_and_answers_once(
    client: TestClient, build: Builder, db_session: Session, settings: Settings
) -> None:
    booked = book(build, db_session)
    headers = headers_for(build, db_session, booked, settings, Role.COORDINATOR)
    request = open_task(db_session, booked, TaskType.RESCHEDULE)

    listed = client.get("/requests", headers=headers).json()
    assert [(item["id"], item["status"]) for item in listed] == [(str(request.id), "pending")]

    new_time = dt.datetime.now(dt.UTC).replace(microsecond=0) + dt.timedelta(days=12)
    approved = client.post(
        f"/requests/{request.id}/approve",
        json={"scheduled_at": new_time.isoformat()},
        headers=headers,
    )

    assert approved.status_code == 200
    assert approved.json()["status"] == "DONE"
    appointment = db_session.get(Appointment, booked.appointment.id)
    assert appointment is not None
    db_session.refresh(appointment)
    assert appointment.scheduled_at == new_time
    again = client.post(f"/requests/{request.id}/decline", headers=headers)
    assert again.status_code == 409
    assert client.get("/requests", headers=headers).json()[0]["status"] == "approved"


def test_declining_a_request_keeps_the_procedure_time(
    client: TestClient, build: Builder, db_session: Session, settings: Settings
) -> None:
    booked = book(build, db_session)
    headers = headers_for(build, db_session, booked, settings, Role.COORDINATOR)
    request = open_task(db_session, booked, TaskType.RESCHEDULE)
    before = booked.appointment.scheduled_at

    declined = client.post(f"/requests/{request.id}/decline", headers=headers)

    assert declined.status_code == 200
    assert declined.json()["status"] == "CANCELLED"
    db_session.refresh(booked.appointment)
    assert booked.appointment.scheduled_at == before


def test_guests_see_requests_but_cannot_answer_them(
    client: TestClient, build: Builder, db_session: Session, settings: Settings
) -> None:
    booked = book(build, db_session)
    guest = headers_for(build, db_session, booked, settings, Role.DEMO_VIEWER)
    request = open_task(db_session, booked, TaskType.RESCHEDULE)

    assert client.get("/requests", headers=guest).status_code == 200
    assert client.post(f"/requests/{request.id}/decline", headers=guest).status_code == 403


def test_badges_count_open_work_by_kind(
    client: TestClient, build: Builder, db_session: Session, settings: Settings
) -> None:
    booked = book(build, db_session)
    headers = headers_for(build, db_session, booked, settings, Role.COORDINATOR)
    before = client.get("/dashboard/badges", headers=headers).json()

    open_task(db_session, booked, TaskType.CALL_PATIENT)
    open_task(db_session, booked, TaskType.RESCHEDULE)
    db_session.add(
        Escalation(
            organization_id=booked.patient.organization_id,
            patient_id=booked.patient.id,
            appointment_id=booked.appointment.id,
            source=EscalationSource.STAFF,
            severity=EscalationSeverity.NORMAL,
            status=EscalationStatus.OPEN,
            summary="Asked about their medicine",
        )
    )
    db_session.flush()
    after = client.get("/dashboard/badges", headers=headers).json()

    assert after["open_tasks"] == before["open_tasks"] + 1
    assert after["pending_requests"] == before["pending_requests"] + 1
    assert after["open_escalations"] == before["open_escalations"] + 1
