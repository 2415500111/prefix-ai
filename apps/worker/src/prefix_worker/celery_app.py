from typing import Any

from celery import Celery
from celery.signals import setup_logging

from prefix_api.core.config import Settings, get_settings
from prefix_api.core.logging import configure_logging

DEMO_PING_INTERVAL_SECONDS = 300.0


def create_celery_app(settings: Settings) -> Celery:
    broker_url = settings.redis_url.unicode_string()
    app = Celery("prefix_worker", broker=broker_url, backend=broker_url)
    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
        task_track_started=True,
        result_expires=3600,
        broker_connection_retry_on_startup=True,
        worker_hijack_root_logger=False,
        beat_schedule={
            "demo-ping": {
                "task": "prefix_worker.demo.ping",
                "schedule": DEMO_PING_INTERVAL_SECONDS,
            },
        },
    )
    app.autodiscover_tasks(["prefix_worker"], related_name="tasks", force=True)
    return app


@setup_logging.connect
def _configure_logging(**_kwargs: Any) -> None:
    # Connecting to this signal stops Celery from installing its own log handlers.
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)


celery_app = create_celery_app(get_settings())
