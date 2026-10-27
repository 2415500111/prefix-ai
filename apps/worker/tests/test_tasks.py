from prefix_worker.celery_app import DEMO_PING_INTERVAL_SECONDS, celery_app
from prefix_worker.tasks import ping


def test_ping_returns_pong_when_run_locally() -> None:
    result = ping.apply()

    assert result.successful()
    assert result.get() == "pong"


def test_ping_is_registered_with_the_app() -> None:
    celery_app.loader.import_default_modules()

    assert "prefix_worker.demo.ping" in celery_app.tasks


def test_beat_schedules_the_demo_task() -> None:
    entry = celery_app.conf.beat_schedule["demo-ping"]

    assert entry["task"] == "prefix_worker.demo.ping"
    assert entry["schedule"] == DEMO_PING_INTERVAL_SECONDS


def test_only_json_is_accepted() -> None:
    assert celery_app.conf.accept_content == ["json"]
    assert celery_app.conf.task_serializer == "json"
