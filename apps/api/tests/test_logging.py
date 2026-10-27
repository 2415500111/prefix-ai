import json
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from prefix_api.core.config import Settings
from prefix_api.main import create_app

type SettingsFactory = Callable[..., Settings]


def test_requests_are_logged_as_json_without_query_string(
    make_settings: SettingsFactory, capsys: pytest.CaptureFixture[str]
) -> None:
    app = create_app(make_settings(log_format="json"))
    with TestClient(app) as client:
        capsys.readouterr()
        client.get("/health?patient_name=Jane", headers={"X-Request-ID": "req-1"})

    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line]
    access = next(line for line in lines if line["event"] == "request.completed")

    assert access["request_id"] == "req-1"
    assert access["path"] == "/health"
    assert access["status_code"] == 200
    assert access["level"] == "info"
    assert "timestamp" in access
    assert "Jane" not in json.dumps(lines)
