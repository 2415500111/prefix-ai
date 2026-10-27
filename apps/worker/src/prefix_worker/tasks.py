from celery import shared_task

from prefix_api.core.logging import get_logger

logger = get_logger(__name__)


@shared_task(name="prefix_worker.demo.ping")
def ping() -> str:
    """Demo task proving the worker, broker, and beat schedule are wired up."""
    logger.info("demo.ping")
    return "pong"
