"""An unreachable database fails requests at once with a clear 503, instead of hanging."""

import time

from api_testkit import make_test_settings
from fastapi.testclient import TestClient

from prefix_api.main import create_app

# Port 1 is never listening, so the connection is refused straight away.
UNREACHABLE_URL = (
    "postgresql+psycopg://prefix:prefix@127.0.0.1:1/prefix_missing"  # pragma: allowlist secret
)


# A wrong password on purpose: the request must fail on the database, not on credentials.
LOGIN = {"email": "admin@example.com", "password": "not-the-password"}  # pragma: allowlist secret


def test_login_fails_fast_when_the_database_is_unreachable() -> None:
    settings = make_test_settings(database_url=UNREACHABLE_URL)

    with TestClient(create_app(settings)) as client:
        started = time.monotonic()
        response = client.post("/auth/login", json=LOGIN)
        elapsed = time.monotonic() - started

    assert response.status_code == 503
    assert response.json()["code"] == "database_unavailable"
    # The connect timeout is 5 seconds; the bound leaves room for test overhead, and is far
    # below the minutes a request used to hang for.
    assert elapsed < 10


def test_the_api_still_starts_and_reports_health_without_a_database() -> None:
    settings = make_test_settings(database_url=UNREACHABLE_URL)

    with TestClient(create_app(settings)) as client:
        assert client.get("/health").json()["status"] == "ok"
