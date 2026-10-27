import datetime as dt

from api_testkit import PASSWORD, Builder, patient_headers, staff_headers
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from prefix_api.core.config import Settings
from prefix_api.core.security import issue_access_token
from prefix_api.db.models import AuditLog, RefreshToken
from prefix_api.domain.enums import AuditAction, Role


def _login(client: TestClient, email: str, password: str = PASSWORD) -> dict[str, str]:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    body: dict[str, str] = response.json()
    return body


def test_login_returns_tokens_that_work(client: TestClient, build: Builder) -> None:
    user = build.user(build.organization(), Role.COORDINATOR)

    tokens = _login(client, user.email.upper())
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})

    assert me.status_code == 200
    assert me.json()["email"] == user.email
    assert me.json()["role"] == "COORDINATOR"


def test_wrong_password_is_rejected_and_audited(
    client: TestClient, build: Builder, db_session: Session
) -> None:
    user = build.user(build.organization())

    response = client.post("/auth/login", json={"email": user.email, "password": "wrong"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"
    failed = db_session.scalars(
        select(AuditLog).where(
            AuditLog.entity_id == user.id, AuditLog.action == AuditAction.LOGIN_FAILED
        )
    ).all()
    assert len(failed) == 1


def test_unknown_email_gets_the_same_error(client: TestClient) -> None:
    response = client.post(
        "/auth/login", json={"email": "nobody@example.com", "password": PASSWORD}
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_inactive_user_cannot_log_in(client: TestClient, build: Builder) -> None:
    user = build.user(build.organization(), active=False)

    response = client.post("/auth/login", json={"email": user.email, "password": PASSWORD})

    assert response.status_code == 401


def test_refresh_rotates_the_refresh_token(client: TestClient, build: Builder) -> None:
    user = build.user(build.organization())
    first = _login(client, user.email)

    second = client.post("/auth/refresh", json={"refresh_token": first["refresh_token"]})

    assert second.status_code == 200
    assert second.json()["refresh_token"] != first["refresh_token"]
    third = client.post("/auth/refresh", json={"refresh_token": second.json()["refresh_token"]})
    assert third.status_code == 200


def test_reusing_a_rotated_refresh_token_revokes_the_whole_family(
    client: TestClient, build: Builder, db_session: Session
) -> None:
    user = build.user(build.organization())
    first = _login(client, user.email)
    second = client.post("/auth/refresh", json={"refresh_token": first["refresh_token"]}).json()

    replay = client.post("/auth/refresh", json={"refresh_token": first["refresh_token"]})
    legitimate = client.post("/auth/refresh", json={"refresh_token": second["refresh_token"]})

    assert replay.status_code == 401
    assert legitimate.status_code == 401
    tokens = db_session.scalars(select(RefreshToken).where(RefreshToken.user_id == user.id)).all()
    assert all(token.revoked_at is not None for token in tokens)
    assert db_session.scalar(
        select(AuditLog).where(
            AuditLog.entity_id == user.id, AuditLog.action == AuditAction.TOKEN_REUSE_DETECTED
        )
    )


def test_logout_revokes_the_refresh_token(client: TestClient, build: Builder) -> None:
    user = build.user(build.organization())
    tokens = _login(client, user.email)

    assert (
        client.post("/auth/logout", json={"refresh_token": tokens["refresh_token"]}).status_code
        == 204
    )
    response = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})

    assert response.status_code == 401


def test_refresh_tokens_are_stored_hashed(
    client: TestClient, build: Builder, db_session: Session
) -> None:
    user = build.user(build.organization())
    tokens = _login(client, user.email)

    stored = db_session.scalars(select(RefreshToken.token_hash)).all()

    assert tokens["refresh_token"] not in stored


def test_missing_and_garbage_tokens_are_rejected(client: TestClient) -> None:
    assert client.get("/auth/me").status_code == 401
    response = client.get("/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_expired_access_token_is_rejected(
    client: TestClient, build: Builder, settings: Settings
) -> None:
    user = build.user(build.organization())
    token, _ = issue_access_token(
        settings,
        user_id=user.id,
        organization_id=user.organization_id,
        role=user.role,
        now=dt.datetime.now(dt.UTC) - dt.timedelta(hours=2),
    )

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_token_signed_with_another_secret_is_rejected(
    client: TestClient, build: Builder, settings: Settings
) -> None:
    user = build.user(build.organization())
    forged = settings.model_copy(update={"jwt_secret": settings.jwt_secret.__class__("f" * 40)})

    response = client.get("/auth/me", headers=staff_headers(forged, user))

    assert response.status_code == 401


def test_deactivating_a_user_invalidates_existing_access_tokens(
    client: TestClient, build: Builder, settings: Settings, db_session: Session
) -> None:
    user = build.user(build.organization())
    headers = staff_headers(settings, user)

    user.is_active = False
    db_session.flush()

    assert client.get("/auth/me", headers=headers).status_code == 401


def test_role_change_invalidates_existing_access_tokens(
    client: TestClient, build: Builder, settings: Settings, db_session: Session
) -> None:
    user = build.user(build.organization(), Role.ADMIN)
    headers = staff_headers(settings, user)

    user.role = Role.VIEWER
    db_session.flush()

    assert client.get("/auth/me", headers=headers).status_code == 401


def test_patient_token_cannot_be_used_as_staff_token(
    client: TestClient, build: Builder, settings: Settings
) -> None:
    patient = build.patient(build.organization())

    response = client.get("/auth/me", headers=patient_headers(settings, patient))

    assert response.status_code == 401
