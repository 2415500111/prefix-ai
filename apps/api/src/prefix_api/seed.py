"""Load development seed data. Run with `python -m prefix_api.seed`."""

from prefix_api.core.config import get_settings
from prefix_api.core.logging import configure_logging, get_logger


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)
    logger = get_logger(__name__)
    if settings.is_production:
        raise SystemExit("Refusing to seed a production database.")
    logger.info("seed.completed", records_created=0)


if __name__ == "__main__":
    main()
