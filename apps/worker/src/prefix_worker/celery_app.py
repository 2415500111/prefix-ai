from typing import Any

from celery import Celery
from celery.schedules import crontab
from celery.signals import setup_logging

from prefix_api.core.config import Settings, get_settings
from prefix_api.core.logging import configure_logging

DEMO_PING_INTERVAL_SECONDS = 300.0
REMINDER_DISPATCH_INTERVAL_SECONDS = 60.0
TRANSLATION_WARM_INTERVAL_SECONDS = 600.0
RISK_REFRESH_INTERVAL_SECONDS = 900.0


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
            "dispatch-reminders": {
                "task": "prefix_worker.reminders.dispatch",
                "schedule": REMINDER_DISPATCH_INTERVAL_SECONDS,
                # A run that misses its slot is pointless: the next one picks everything up.
                "options": {"expires": REMINDER_DISPATCH_INTERVAL_SECONDS},
            },
            "refresh-risk-scores": {
                "task": "prefix_worker.risk.refresh",
                "schedule": RISK_REFRESH_INTERVAL_SECONDS,
                "options": {"expires": RISK_REFRESH_INTERVAL_SECONDS},
            },
            # The guest demo starts fresh every night at 03:00 in India (21:30 UTC).
            "reset-demo-nightly": {
                "task": "prefix_worker.demo.reset",
                "schedule": crontab(hour=21, minute=30),
            },
            "warm-translations": {
                "task": "prefix_worker.translations.warm",
                "schedule": TRANSLATION_WARM_INTERVAL_SECONDS,
                "options": {"expires": TRANSLATION_WARM_INTERVAL_SECONDS},
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
