"""Protocol safety triggers and step embeddings.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-27

Safety rule (a) at the database level:
- APPROVED and RETIRED protocol versions are immutable (the only allowed change is
  APPROVED -> RETIRED) and cannot be deleted; neither can their steps.
- A patient timeline event can only reference a step of an APPROVED protocol.
"""

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PROTOCOL_GUARD = """
CREATE FUNCTION prep_protocol_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD.status <> 'DRAFT' THEN
            RAISE EXCEPTION 'protocol version % is % and cannot be deleted', OLD.version, OLD.status
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        RETURN OLD;
    END IF;
    IF OLD.status = 'DRAFT' THEN
        RETURN NEW;
    END IF;
    IF OLD.status = 'APPROVED' AND NEW.status = 'RETIRED'
       AND (NEW.organization_id, NEW.family_id, NEW.version, NEW.procedure_type_id, NEW.name,
            NEW.description, NEW.is_sample, NEW.approved_by_id, NEW.approved_at)
           IS NOT DISTINCT FROM
           (OLD.organization_id, OLD.family_id, OLD.version, OLD.procedure_type_id, OLD.name,
            OLD.description, OLD.is_sample, OLD.approved_by_id, OLD.approved_at) THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'protocol version % is % and cannot be changed; create a new draft',
        OLD.version, OLD.status USING ERRCODE = 'insufficient_privilege';
END;
$$
"""

_STEP_GUARD = """
CREATE FUNCTION prep_step_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    protocol_status text;
BEGIN
    IF TG_OP IN ('UPDATE', 'DELETE') THEN
        SELECT status INTO protocol_status FROM prep_protocol WHERE id = OLD.protocol_id;
        IF protocol_status IS NOT NULL AND protocol_status <> 'DRAFT' THEN
            RAISE EXCEPTION 'steps of a % protocol cannot be changed', protocol_status
                USING ERRCODE = 'insufficient_privilege';
        END IF;
    END IF;
    IF TG_OP IN ('INSERT', 'UPDATE') THEN
        SELECT status INTO protocol_status FROM prep_protocol WHERE id = NEW.protocol_id;
        IF protocol_status IS DISTINCT FROM 'DRAFT' THEN
            RAISE EXCEPTION 'steps can only be added to a DRAFT protocol'
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        RETURN NEW;
    END IF;
    RETURN OLD;
END;
$$
"""

_TIMELINE_GUARD = """
CREATE FUNCTION timeline_event_requires_approved_step() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM prep_step s JOIN prep_protocol p ON p.id = s.protocol_id
        WHERE s.id = NEW.step_id AND p.status = 'APPROVED'
    ) THEN
        RAISE EXCEPTION 'timeline events may only use steps of an APPROVED protocol'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END;
$$
"""


def upgrade() -> None:
    op.add_column(
        "prep_step",
        sa.Column("embedding", pgvector.sqlalchemy.Vector(dim=384), nullable=True),
    )
    op.add_column("prep_step", sa.Column("embedding_model", sa.String(length=64), nullable=True))

    op.execute(_PROTOCOL_GUARD)
    op.execute(
        "CREATE TRIGGER prep_protocol_guard BEFORE UPDATE OR DELETE ON prep_protocol "
        "FOR EACH ROW EXECUTE FUNCTION prep_protocol_guard()"
    )
    op.execute(_STEP_GUARD)
    op.execute(
        "CREATE TRIGGER prep_step_guard BEFORE INSERT OR UPDATE OR DELETE ON prep_step "
        "FOR EACH ROW EXECUTE FUNCTION prep_step_guard()"
    )
    op.execute(_TIMELINE_GUARD)
    op.execute(
        "CREATE TRIGGER timeline_event_requires_approved_step "
        "BEFORE INSERT OR UPDATE OF step_id ON patient_timeline_event "
        "FOR EACH ROW EXECUTE FUNCTION timeline_event_requires_approved_step()"
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS timeline_event_requires_approved_step ON patient_timeline_event"
    )
    op.execute("DROP FUNCTION IF EXISTS timeline_event_requires_approved_step()")
    op.execute("DROP TRIGGER IF EXISTS prep_step_guard ON prep_step")
    op.execute("DROP FUNCTION IF EXISTS prep_step_guard()")
    op.execute("DROP TRIGGER IF EXISTS prep_protocol_guard ON prep_protocol")
    op.execute("DROP FUNCTION IF EXISTS prep_protocol_guard()")
    op.drop_column("prep_step", "embedding_model")
    op.drop_column("prep_step", "embedding")
