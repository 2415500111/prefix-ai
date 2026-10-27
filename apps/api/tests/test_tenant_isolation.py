"""A user in one organization can never see or change another organization's data."""

import pytest
from api_testkit import Builder, patient_headers, staff_headers
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from prefix_api.core.config import Settings
from prefix_api.db.models import Patient
from prefix_api.domain.enums import Role


@pytest.fixture
def two_orgs(build: Builder, settings: Settings) -> tuple[Patient, dict[str, str]]:
    """A patient in org A, and admin credentials for org B."""
    org_a, org_b = build.organization("A"), build.organization("B")
    patient_a = build.patient(org_a, phone="+919800000001", email="a@example.com")
    return patient_a, staff_headers(settings, build.user(org_b, Role.ADMIN))


def test_cannot_read_another_orgs_patient(
    client: TestClient, two_orgs: tuple[Patient, dict[str, str]]
) -> None:
    patient_a, headers_b = two_orgs

    response = client.get(f"/patients/{patient_a.id}", headers=headers_b)

    # 404 rather than 403, so the record's existence is not revealed.
    assert response.status_code == 404


def test_cannot_update_another_orgs_patient(
    client: TestClient, two_orgs: tuple[Patient, dict[str, str]], db_session: Session
) -> None:
    patient_a, headers_b = two_orgs

    response = client.patch(
        f"/patients/{patient_a.id}", json={"on_anticoagulant": True}, headers=headers_b
    )

    assert response.status_code == 404
    db_session.expire_all()
    assert db_session.get(Patient, patient_a.id).on_anticoagulant is False  # type: ignore[union-attr]


def test_list_only_returns_own_org(
    client: TestClient, two_orgs: tuple[Patient, dict[str, str]]
) -> None:
    patient_a, headers_b = two_orgs

    response = client.get("/patients", headers=headers_b)

    assert response.status_code == 200
    assert str(patient_a.id) not in {p["id"] for p in response.json()}


def test_search_by_identifier_does_not_cross_orgs(
    client: TestClient, two_orgs: tuple[Patient, dict[str, str]]
) -> None:
    _, headers_b = two_orgs

    response = client.post("/patients/search", json={"phone": "+919800000001"}, headers=headers_b)

    assert response.status_code == 200
    assert response.json() == []


def test_cannot_issue_magic_link_for_another_orgs_patient(
    client: TestClient, two_orgs: tuple[Patient, dict[str, str]]
) -> None:
    patient_a, headers_b = two_orgs

    response = client.post(f"/patients/{patient_a.id}/magic-links", headers=headers_b)

    assert response.status_code == 404


def test_created_records_belong_to_the_creators_org(
    client: TestClient, build: Builder, settings: Settings, db_session: Session
) -> None:
    org = build.organization()
    headers = staff_headers(settings, build.user(org, Role.COORDINATOR))

    response = client.post(
        "/patients",
        json={"first_name": "Ravi", "last_name": "K", "date_of_birth": "1980-01-01"},
        headers=headers,
    )

    created = db_session.scalar(select(Patient).where(Patient.id == response.json()["id"]))
    assert created is not None
    assert created.organization_id == org.id


def test_organization_id_cannot_be_injected_in_body(
    client: TestClient, build: Builder, settings: Settings
) -> None:
    org, other = build.organization(), build.organization()
    headers = staff_headers(settings, build.user(org, Role.COORDINATOR))

    response = client.post(
        "/patients",
        json={
            "first_name": "Ravi",
            "last_name": "K",
            "date_of_birth": "1980-01-01",
            "organization_id": str(other.id),
        },
        headers=headers,
    )

    assert response.status_code == 422


def test_users_and_facilities_are_scoped(
    client: TestClient, build: Builder, settings: Settings
) -> None:
    org_a, org_b = build.organization(), build.organization()
    build.facility(org_a)
    user_a = build.user(org_a)
    headers_b = staff_headers(settings, build.user(org_b, Role.ADMIN))

    users = client.get("/users", headers=headers_b).json()
    facilities = client.get("/facilities", headers=headers_b).json()

    assert user_a.email not in {u["email"] for u in users}
    assert facilities == []


def test_patient_session_only_reaches_own_record(
    client: TestClient, build: Builder, settings: Settings
) -> None:
    org = build.organization()
    patient = build.patient(org, first_name="Meera")

    response = client.get("/patient/me", headers=patient_headers(settings, patient))

    assert response.status_code == 200
    assert response.json()["id"] == str(patient.id)
    assert response.json()["first_name"] == "Meera"
