import datetime as dt

from api_testkit import Builder, staff_headers
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from prefix_api.core.config import Settings
from prefix_api.db.models import PatientMagicLink
from prefix_api.domain.enums import Role


def _issue(client: TestClient, build: Builder, settings: Settings) -> tuple[str, str]:
    org = build.organization()
    patient = build.patient(org)
    response = client.post(
        f"/patients/{patient.id}/magic-links",
        headers=staff_headers(settings, build.user(org, Role.NURSE)),
    )
    assert response.status_code == 201, response.text
    url: str = response.json()["url"]
    return str(patient.id), url.split("#token=", 1)[1]


def test_magic_link_puts_token_in_url_fragment(
    client: TestClient, build: Builder, settings: Settings
) -> None:
    org = build.organization()
    patient = build.patient(org)

    response = client.post(
        f"/patients/{patient.id}/magic-links",
        headers=staff_headers(settings, build.user(org, Role.COORDINATOR)),
    )

    assert response.json()["url"].startswith("http://localhost:3000/p#token=")


def test_redeemed_link_gives_a_patient_session(
    client: TestClient, build: Builder, settings: Settings
) -> None:
    patient_id, token = _issue(client, build, settings)

    session = client.post("/patient/session", json={"token": token})
    me = client.get(
        "/patient/me", headers={"Authorization": f"Bearer {session.json()['access_token']}"}
    )

    assert session.status_code == 200
    assert me.status_code == 200
    assert me.json()["id"] == patient_id


def test_link_is_single_use(client: TestClient, build: Builder, settings: Settings) -> None:
    _, token = _issue(client, build, settings)

    first = client.post("/patient/session", json={"token": token})
    second = client.post("/patient/session", json={"token": token})

    assert first.status_code == 200
    assert second.status_code == 401


def test_expired_link_is_rejected(
    client: TestClient, build: Builder, settings: Settings, db_session: Session
) -> None:
    _, token = _issue(client, build, settings)
    db_session.execute(
        update(PatientMagicLink).values(
            expires_at=dt.datetime.now(dt.UTC) - dt.timedelta(minutes=1)
        )
    )

    response = client.post("/patient/session", json={"token": token})

    assert response.status_code == 401


def test_unknown_token_is_rejected(client: TestClient) -> None:
    response = client.post("/patient/session", json={"token": "x" * 43})

    assert response.status_code == 401


def test_only_the_token_hash_is_stored(
    client: TestClient, build: Builder, settings: Settings, db_session: Session
) -> None:
    _, token = _issue(client, build, settings)

    assert token not in db_session.scalars(select(PatientMagicLink.token_hash)).all()


def test_patient_session_cannot_reach_staff_endpoints(
    client: TestClient, build: Builder, settings: Settings
) -> None:
    patient_id, token = _issue(client, build, settings)
    access = client.post("/patient/session", json={"token": token}).json()["access_token"]
    headers = {"Authorization": f"Bearer {access}"}

    assert client.get(f"/patients/{patient_id}", headers=headers).status_code == 401
    assert client.get("/patients", headers=headers).status_code == 401


def test_staff_token_cannot_reach_patient_endpoints(
    client: TestClient, build: Builder, settings: Settings
) -> None:
    org = build.organization()

    response = client.get("/patient/me", headers=staff_headers(settings, build.user(org)))

    assert response.status_code == 401
