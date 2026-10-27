import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from prefix_api.core.security import verify_password
from prefix_api.db.models import Facility, Organization, ProcedureType, User
from prefix_api.seed import DEMO_ADMIN_EMAIL, DEMO_ORG_SLUG, PROCEDURE_TYPES, seed


def test_seed_creates_demo_org_and_is_idempotent(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SEED_ADMIN_PASSWORD", "seed-password-123")

    first = seed(db_session)
    second = seed(db_session)

    assert first == "seed-password-123"
    assert second is None
    org = db_session.scalar(select(Organization).where(Organization.slug == DEMO_ORG_SLUG))
    assert org is not None
    count = db_session.scalar(
        select(func.count())
        .select_from(ProcedureType)
        .where(ProcedureType.organization_id == org.id)
    )
    assert count == len(PROCEDURE_TYPES)
    assert (db_session.scalar(select(func.count()).select_from(Facility)) or 0) >= 1
    admin = db_session.scalar(select(User).where(User.email == DEMO_ADMIN_EMAIL))
    assert admin is not None
    assert verify_password("seed-password-123", admin.password_hash)
