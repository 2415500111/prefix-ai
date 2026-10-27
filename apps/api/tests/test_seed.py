import re

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from prefix_api.core.security import verify_password
from prefix_api.db.models import Facility, Organization, PrepProtocol, ProcedureType, User
from prefix_api.domain.enums import ProtocolStatus, StepCategory
from prefix_api.sample_protocols import SAMPLE_LABEL, SAMPLE_PROTOCOLS, SampleProtocol
from prefix_api.schemas.protocols import StepIn
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


def test_seed_adds_sample_protocols_as_labelled_drafts(db_session: Session) -> None:
    seed(db_session)
    seed(db_session)

    org = db_session.scalar(select(Organization).where(Organization.slug == DEMO_ORG_SLUG))
    assert org is not None
    protocols = db_session.scalars(
        select(PrepProtocol).where(PrepProtocol.organization_id == org.id)
    ).all()
    assert len(protocols) == len(SAMPLE_PROTOCOLS)
    for protocol in protocols:
        assert protocol.status is ProtocolStatus.DRAFT
        assert protocol.is_sample
        assert SAMPLE_LABEL in protocol.name
        assert protocol.description is not None
        assert SAMPLE_LABEL in protocol.description
        assert protocol.steps


@pytest.mark.parametrize("sample", SAMPLE_PROTOCOLS, ids=lambda s: s.procedure_code)
def test_sample_protocol_content_is_well_formed(sample: SampleProtocol) -> None:
    for step in sample.steps:
        StepIn(
            offset_minutes=step.offset_minutes,
            title=step.title,
            instruction_text=step.instruction_text,
            category=step.category,
            requires_confirmation=step.requires_confirmation,
            is_critical=step.is_critical,
            conditions=step.conditions,
        )
        # Samples never prescribe: no doses, and medicine steps defer to the care team.
        assert not re.search(r"\d+\s?(mg|ml|units?|tablets?)\b", step.instruction_text, re.I)
        if step.category is StepCategory.MEDICATION:
            assert "care team" in step.instruction_text
