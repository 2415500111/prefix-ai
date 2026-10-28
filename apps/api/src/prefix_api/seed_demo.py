"""Create or refresh the guest demo hospital. Run with `make seed-demo` (or the command below).

    uv run python -m prefix_api.seed_demo

Safe to re-run: it regenerates the synthetic patients, bookings and reminders, and keeps the
demo's staff accounts and approved protocols. It refuses to run in production. The demo
admin's password is printed only when the account is first created; set DEMO_ADMIN_PASSWORD
to choose it.
"""

import datetime as dt
import os
import secrets
import sys

from prefix_api.core.config import get_settings
from prefix_api.core.crypto import configure_crypto
from prefix_api.core.logging import configure_logging
from prefix_api.db.session import create_db_engine, create_session_factory
from prefix_api.services.demo import (
    DEMO_EMAIL_DOMAIN,
    DEMO_SLUG,
    demo_organization,
    populate_demo,
)


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)
    configure_crypto(settings)
    if settings.is_production:
        sys.exit("Refusing to seed the demo hospital in production.")

    engine = create_db_engine(settings)
    try:
        factory = create_session_factory(engine)
        with factory() as session:
            existed = demo_organization(session) is not None
        password = os.environ.get("DEMO_ADMIN_PASSWORD") or secrets.token_urlsafe(12)
        result = populate_demo(factory, now=dt.datetime.now(dt.UTC), admin_password=password)
    finally:
        engine.dispose()

    print(  # noqa: T201 - a developer-facing summary
        f"Demo hospital ready: {result.patients} patients, {result.appointments} bookings, "
        f"{result.reminders_sent} reminders, {result.answers} answers, "
        f"{result.escalations} escalations."
    )
    print("Guest sign-in: the 'Try as Guest' button at http://localhost:3000/login")  # noqa: T201
    if not existed:
        print(  # noqa: T201
            f"Demo admin (resets the demo): admin@{DEMO_SLUG}.{DEMO_EMAIL_DOMAIN} / {password}"
        )


if __name__ == "__main__":
    main()
