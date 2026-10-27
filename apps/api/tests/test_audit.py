"""Safety rule (d): every read and write of patient data is audit-logged."""

import pytest
from api_testkit import Builder, patient_headers, staff_headers
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from prefix_api.api.deps import patient_data_route
from prefix_api.core.config import Settings
from prefix_api.db.models import AuditLog
from prefix_api.domain.enums import ActorType, AuditAction, Role


def _audits(session: Session, **filters: object) -> list[AuditLog]:
    query = select(AuditLog).order_by(AuditLog.id)
    for column, value in filters.items():
        query = query.where(getattr(AuditLog, column) == value)
    return list(session.scalars(query))


def test_reading_a_patient_is_audited_with_full_context(
    client: TestClient, build: Builder, settings: Settings, db_session: Session
) -> None:
    org = build.organization()
    user = build.user(org, Role.NURSE)
    patient = build.patient(org)

    client.get(
        f"/patients/{patient.id}",
        headers={
            **staff_headers(settings, user),
            "X-Request-ID": "req-audit-1",
            "User-Agent": "UA/1",
        },
    )

    [entry] = _audits(db_session, patient_id=patient.id)
    assert entry.action == AuditAction.READ
    assert entry.actor_type == ActorType.USER
    assert entry.actor_id == user.id
    assert entry.organization_id == org.id
    assert entry.entity_type == "patient"
    assert entry.entity_id == patient.id
    assert entry.purpose == "patient_view"
    assert entry.request_id == "req-audit-1"
    assert entry.user_agent == "UA/1"
    assert entry.ip_address


@pytest.mark.parametrize(
    ("method", "path", "body", "action"),
    [
        ("GET", "/patients", None, AuditAction.LIST),
        ("PATCH", "/patients/{id}", {"diabetic_on_insulin": True}, AuditAction.UPDATE),
        ("POST", "/patients/{id}/magic-links", None, AuditAction.MAGIC_LINK_ISSUED),
    ],
)
def test_patient_endpoints_write_audit_rows(
    client: TestClient,
    build: Builder,
    settings: Settings,
    db_session: Session,
    method: str,
    path: str,
    body: dict[str, object] | None,
    action: AuditAction,
) -> None:
    org = build.organization()
    patient = build.patient(org)
    headers = staff_headers(settings, build.user(org, Role.ADMIN))

    response = client.request(method, path.format(id=patient.id), json=body, headers=headers)

    assert response.status_code < 300
    assert [e.action for e in _audits(db_session, patient_id=patient.id)] == [action]


def test_create_and_search_are_audited(
    client: TestClient, build: Builder, settings: Settings, db_session: Session
) -> None:
    org = build.organization()
    headers = staff_headers(settings, build.user(org, Role.COORDINATOR))

    created = client.post(
        "/patients",
        json={
            "first_name": "Ravi",
            "last_name": "Kumar",
            "date_of_birth": "1980-02-03",
            "phone": "+919811111111",
        },
        headers=headers,
    ).json()
    found = client.post("/patients/search", json={"phone": "+919811111111"}, headers=headers)

    assert [p["id"] for p in found.json()] == [created["id"]]
    actions = [e.action for e in _audits(db_session, patient_id=created["id"])]
    assert actions == [AuditAction.CREATE, AuditAction.LIST]


def test_update_audit_records_field_names_but_never_values(
    client: TestClient, build: Builder, settings: Settings, db_session: Session
) -> None:
    org = build.organization()
    patient = build.patient(org)
    headers = staff_headers(settings, build.user(org, Role.ADMIN))

    client.patch(
        f"/patients/{patient.id}",
        json={"first_name": "Secretname", "phone": "+919822222222"},
        headers=headers,
    )

    [entry] = _audits(db_session, patient_id=patient.id)
    assert entry.details == {"fields": ["first_name", "phone"]}
    raw = db_session.execute(
        text("SELECT details::text FROM audit_log WHERE id = :id"), {"id": entry.id}
    )
    assert "Secretname" not in raw.scalar_one()


def test_patient_self_access_is_audited_as_patient(
    client: TestClient, build: Builder, settings: Settings, db_session: Session
) -> None:
    patient = build.patient(build.organization())

    client.get("/patient/me", headers=patient_headers(settings, patient))

    [entry] = _audits(db_session, patient_id=patient.id)
    assert entry.actor_type == ActorType.PATIENT
    assert entry.actor_id == patient.id
    assert entry.purpose == "patient_self_access"


def test_denied_requests_do_not_count_as_access(
    client: TestClient, build: Builder, settings: Settings, db_session: Session
) -> None:
    org = build.organization()
    patient = build.patient(org)

    client.get(
        f"/patients/{patient.id}", headers=staff_headers(settings, build.user(org, Role.VIEWER))
    )

    assert _audits(db_session, patient_id=patient.id) == []


def test_audit_log_is_append_only(build: Builder, db_session: Session) -> None:
    org = build.organization()
    db_session.add(
        AuditLog(
            organization_id=org.id,
            actor_type=ActorType.SYSTEM,
            action=AuditAction.READ,
            entity_type="patient",
            purpose="test",
            details={},
        )
    )
    db_session.flush()

    with pytest.raises(DBAPIError, match="append-only"), db_session.begin_nested():
        db_session.execute(text("UPDATE audit_log SET purpose = 'tampered'"))
    with pytest.raises(DBAPIError, match="append-only"), db_session.begin_nested():
        db_session.execute(text("DELETE FROM audit_log"))


def test_backstop_audits_patient_routes_that_forget(
    app: FastAPI, build: Builder, db_session: Session
) -> None:
    @app.get("/test-forgetful-route", dependencies=[Depends(patient_data_route)])
    def forgetful() -> dict[str, str]:
        return {"ok": "true"}

    with TestClient(app) as client:
        response = client.get("/test-forgetful-route", headers={"X-Request-ID": "req-forgot"})

    assert response.status_code == 200
    [entry] = _audits(db_session, request_id="req-forgot")
    assert entry.purpose == "audit_backstop"
