"""Release hardening: password guessing is limited, responses carry security headers, and
personal details never reach the logs."""

import json
from collections.abc import Callable

import pytest
from api_testkit import PASSWORD, Builder
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from prefix_api.core.config import Settings
from prefix_api.domain.enums import Role
from prefix_api.main import create_app

type SettingsFactory = Callable[..., Settings]

GUESS = "wrong-guess"  # pragma: allowlist secret
MARKER_PASSWORD = "pii-marker-pass"  # pragma: allowlist secret


def test_repeated_wrong_passwords_are_limited_per_account(client: TestClient) -> None:
    for _ in range(10):
        response = client.post(
            "/auth/login", json={"email": "nobody@example.com", "password": GUESS}
        )
        assert response.status_code == 401

    # The same account, written differently, shares the allowance.
    blocked = client.post("/auth/login", json={"email": " Nobody@Example.com ", "password": GUESS})

    assert blocked.status_code == 429


def test_ordinary_sign_ins_are_never_limited(client: TestClient, build: Builder) -> None:
    org = build.organization()
    user = build.user(org, Role.COORDINATOR)

    statuses = [
        client.post("/auth/login", json={"email": user.email, "password": PASSWORD}).status_code
        for _ in range(12)
    ]

    assert statuses == [200] * 12


def test_responses_refuse_framing_sniffing_and_caching(client: TestClient) -> None:
    health = client.get("/health")
    missing = client.get("/no-such-route")

    for response in (health, missing):
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["Referrer-Policy"] == "no-referrer"
        assert response.headers["Cache-Control"] == "no-store"
        assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    # HSTS is for HTTPS deployments only; a local test server must not pin it.
    assert "Strict-Transport-Security" not in health.headers


def test_production_adds_strict_transport_security(
    make_settings: SettingsFactory, session_factory: sessionmaker[Session]
) -> None:
    app = create_app(make_settings(app_env="production"), session_factory=session_factory)
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.headers["Strict-Transport-Security"] == "max-age=31536000; includeSubDomains"


def test_personal_details_never_reach_the_logs(
    make_settings: SettingsFactory, capsys: pytest.CaptureFixture[str]
) -> None:
    app = create_app(make_settings(log_format="json"))
    with TestClient(app) as client:
        capsys.readouterr()
        client.post(
            "/auth/login",
            json={"email": "pii-marker-7731@example.com", "password": MARKER_PASSWORD},
        )
        client.post(
            "/auth/login",
            json={"email": "pii-marker-7731@example.com", "password": ""},
        )

    output = capsys.readouterr().out
    lines = [json.loads(line) for line in output.splitlines() if line]
    assert any(line["event"] == "request.completed" for line in lines)
    assert "pii-marker" not in output
