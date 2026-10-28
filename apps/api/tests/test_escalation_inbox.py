"""The nurse inbox: urgent first, acknowledge and resolve, and who may see it (safety rule d)."""

import datetime as dt

from api_testkit import Builder, patient_headers, staff_headers
from fastapi.testclient import TestClient
from messaging_testkit import Booked, book
from sqlalchemy import select
from sqlalchemy.orm import Session

from prefix_api.core.config import Settings
from prefix_api.db.models import AuditLog, Escalation, Organization, Task
from prefix_api.domain.enums import (
    ActorType,
    AuditAction,
    EscalationSeverity,
    EscalationSource,
    Role,
    TaskStatus,
    TaskType,
)
from prefix_api.services.check_ins import create_escalation


def org_of(db_session: Session, booked: Booked) -> Organization:
    org = db_session.get(Organization, booked.patient.organization_id)
    assert org is not None
    return org


def open_escalation(
    db_session: Session, booked: Booked, severity: EscalationSeverity, summary: str
) -> Escalation:
    """A real escalation row, written the way the assistant and check-ins write them."""
    from prefix_api.domain.principal import SystemPrincipal

    principal = SystemPrincipal(organization_id=booked.patient.organization_id, job="test")
    escalation = create_escalation(
        db_session,
        principal=principal,
        patient=booked.patient,
        appointment=booked.appointment,
        severity=severity,
        summary=summary,
        purpose="test",
        source=EscalationSource.RED_FLAG,
    )
    db_session.flush()
    return escalation


def nurse_headers(
    build: Builder,
    db_session: Session,
    booked: Booked,
    settings: Settings,
    role: Role = Role.NURSE,
) -> dict[str, str]:
    user = build.user(org_of(db_session, booked), role)
    return staff_headers(settings, user)


def test_inbox_lists_the_most_urgent_first(
    client: TestClient, settings: Settings, build: Builder, db_session: Session
) -> None:
    # One booking, so both escalations belong to the same hospital as the nurse.
    booked = book(build, db_session)
    normal = open_escalation(db_session, booked, EscalationSeverity.NORMAL, "Asked for help")
    urgent = open_escalation(db_session, booked, EscalationSeverity.URGENT, "Chest pain")

    response = client.get(
        "/escalations", headers=nurse_headers(build, db_session, booked, settings)
    )

    assert response.status_code == 200
    ids = [row["id"] for row in response.json()]
    assert ids.index(str(urgent.id)) < ids.index(str(normal.id))
    urgent_row = next(row for row in response.json() if row["id"] == str(urgent.id))
    assert urgent_row["patient_name"] == f"{booked.patient.first_name} {booked.patient.last_name}"
    assert urgent_row["procedure_name"] == "Colonoscopy"
    assert urgent_row["status"] == "OPEN"


def test_acknowledge_then_resolve_closes_the_follow_up_tasks(
    client: TestClient, settings: Settings, build: Builder, db_session: Session
) -> None:
    booked = book(build, db_session)
    escalation = open_escalation(db_session, booked, EscalationSeverity.URGENT, "Chest pain")
    task = Task(
        organization_id=booked.patient.organization_id,
        type=TaskType.CALL_PATIENT,
        title="Call the patient",
        patient_id=booked.patient.id,
        escalation_id=escalation.id,
        due_at=dt.datetime.now(dt.UTC),
    )
    db_session.add(task)
    db_session.flush()
    headers = nurse_headers(build, db_session, booked, settings)

    acknowledged = client.post(f"/escalations/{escalation.id}/acknowledge", headers=headers)
    assert acknowledged.status_code == 200
    assert acknowledged.json()["status"] == "ACKNOWLEDGED"

    resolved = client.post(
        f"/escalations/{escalation.id}/resolve",
        headers=headers,
        json={"note": "Called. Patient is safe and attending A&E."},
    )

    assert resolved.status_code == 200
    body = resolved.json()
    assert body["status"] == "RESOLVED"
    assert body["resolution_note"] == "Called. Patient is safe and attending A&E."
    db_session.refresh(task)
    assert task.status is TaskStatus.DONE
    open_list = client.get("/escalations", headers=headers).json()
    assert str(escalation.id) not in [row["id"] for row in open_list]
    resolved_list = client.get("/escalations?status=resolved", headers=headers).json()
    assert str(escalation.id) in [row["id"] for row in resolved_list]


def test_resolving_twice_is_a_conflict(
    client: TestClient, settings: Settings, build: Builder, db_session: Session
) -> None:
    booked = book(build, db_session)
    escalation = open_escalation(db_session, booked, EscalationSeverity.NORMAL, "Question")
    headers = nurse_headers(build, db_session, booked, settings)
    client.post(f"/escalations/{escalation.id}/resolve", headers=headers, json={"note": "Done"})

    again = client.post(
        f"/escalations/{escalation.id}/resolve", headers=headers, json={"note": "Again"}
    )

    assert again.status_code == 409


def test_a_resolution_needs_a_note(
    client: TestClient, settings: Settings, build: Builder, db_session: Session
) -> None:
    booked = book(build, db_session)
    escalation = open_escalation(db_session, booked, EscalationSeverity.NORMAL, "Question")

    response = client.post(
        f"/escalations/{escalation.id}/resolve",
        headers=nurse_headers(build, db_session, booked, settings),
        json={"note": "   "},
    )

    assert response.status_code == 422


def test_viewers_cannot_see_the_inbox(
    client: TestClient, settings: Settings, build: Builder, db_session: Session
) -> None:
    booked = book(build, db_session)
    open_escalation(db_session, booked, EscalationSeverity.URGENT, "Chest pain")

    response = client.get(
        "/escalations", headers=nurse_headers(build, db_session, booked, settings, Role.VIEWER)
    )

    assert response.status_code == 403


def test_another_organisations_escalation_is_not_found(
    client: TestClient, settings: Settings, build: Builder, db_session: Session
) -> None:
    theirs = book(build, db_session)
    foreign = open_escalation(db_session, theirs, EscalationSeverity.URGENT, "Chest pain")
    stranger = build.user(build.organization("Other"), Role.NURSE)

    response = client.post(
        f"/escalations/{foreign.id}/acknowledge", headers=staff_headers(settings, stranger)
    )

    assert response.status_code == 404


def test_reading_the_inbox_is_audited_as_the_staff_member(
    client: TestClient, settings: Settings, build: Builder, db_session: Session
) -> None:
    booked = book(build, db_session)
    escalation = open_escalation(db_session, booked, EscalationSeverity.URGENT, "Chest pain")

    client.get("/escalations", headers=nurse_headers(build, db_session, booked, settings))

    rows = db_session.scalars(
        select(AuditLog).where(
            AuditLog.entity_id == escalation.id,
            AuditLog.actor_type == ActorType.USER,
            AuditLog.action == AuditAction.LIST,
        )
    ).all()
    assert len(rows) == 1
    assert rows[0].patient_id == booked.patient.id
    assert rows[0].purpose == "escalation_handling"


def test_patients_cannot_use_the_inbox(
    client: TestClient, settings: Settings, build: Builder, db_session: Session
) -> None:
    booked = book(build, db_session)

    response = client.get("/escalations", headers=patient_headers(settings, booked.patient))

    assert response.status_code == 401
