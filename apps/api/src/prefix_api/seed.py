"""Load development seed data. Run with `python -m prefix_api.seed` (or `make seed`).

Idempotent: re-running leaves existing rows alone. Refuses to run in production.
"""

import os
import secrets
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from prefix_api.core.config import get_settings
from prefix_api.core.crypto import configure_crypto
from prefix_api.core.logging import configure_logging, get_logger
from prefix_api.core.security import hash_password
from prefix_api.db.models import Facility, Organization, ProcedureType, User
from prefix_api.db.session import create_db_engine, create_session_factory
from prefix_api.domain.enums import Role

DEMO_ORG_SLUG = "demo-hospital"
DEMO_ADMIN_EMAIL = "admin@demo-hospital.example.com"

PROCEDURE_TYPES = [
    # code, name, default minutes, OR cost per minute (INR), sedation
    ("COLONOSCOPY", "Colonoscopy", 45, Decimal("150.00"), True),
    ("GENERAL_SURGERY", "General surgery under anesthesia", 120, Decimal("600.00"), True),
    ("CT_CONTRAST", "CT scan with contrast", 30, Decimal("100.00"), False),
    ("MRI", "MRI scan", 45, Decimal("120.00"), False),
]


def seed(session: Session) -> str | None:
    """Create the demo org. Returns the admin password if the admin was just created."""
    org = session.scalar(select(Organization).where(Organization.slug == DEMO_ORG_SLUG))
    if org is None:
        org = Organization(
            name="Demo Hospital",
            slug=DEMO_ORG_SLUG,
            country_code="IN",
            default_timezone="Asia/Kolkata",
        )
        session.add(org)
        session.flush()

    if session.scalar(select(Facility).where(Facility.organization_id == org.id)) is None:
        session.add(
            Facility(
                organization_id=org.id,
                name="Main Campus",
                timezone="Asia/Kolkata",
                address="1 Demo Road, Bengaluru",
            )
        )

    existing_codes = set(
        session.scalars(select(ProcedureType.code).where(ProcedureType.organization_id == org.id))
    )
    for code, name, minutes, cost, sedation in PROCEDURE_TYPES:
        if code not in existing_codes:
            session.add(
                ProcedureType(
                    organization_id=org.id,
                    code=code,
                    name=name,
                    default_duration_minutes=minutes,
                    or_cost_per_minute=cost,
                    requires_sedation=sedation,
                )
            )

    password: str | None = None
    if session.scalar(select(User).where(User.email == DEMO_ADMIN_EMAIL)) is None:
        password = os.environ.get("SEED_ADMIN_PASSWORD") or secrets.token_urlsafe(12)
        session.add(
            User(
                organization_id=org.id,
                email=DEMO_ADMIN_EMAIL,
                full_name="Demo Admin",
                role=Role.ADMIN,
                password_hash=hash_password(password),
            )
        )
    session.commit()
    return password


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)
    configure_crypto(settings)
    logger = get_logger(__name__)
    if settings.is_production:
        raise SystemExit("Refusing to seed a production database.")

    engine = create_db_engine(settings)
    try:
        with create_session_factory(engine)() as session:
            password = seed(session)
    finally:
        engine.dispose()

    logger.info("seed.completed", admin_email=DEMO_ADMIN_EMAIL)
    if password is not None:
        # Development only: printed once so the developer can log in.
        print(f"Demo admin: {DEMO_ADMIN_EMAIL} / {password}")  # noqa: T201


if __name__ == "__main__":
    main()
