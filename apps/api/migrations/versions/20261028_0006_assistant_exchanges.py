"""AI Prep Assistant exchanges (question, reply, outcome, citations, escalation link).

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-28 10:31:11.235405
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "assistant_exchange",
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("appointment_id", sa.Uuid(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("reply", sa.Text(), nullable=False),
        sa.Column("language", sa.String(length=8), nullable=False),
        sa.Column(
            "outcome",
            sa.Enum(
                "ANSWERED",
                "RED_FLAG",
                "OUT_OF_PROTOCOL",
                "NOT_COVERED",
                "CHECK_FAILED",
                "UNAVAILABLE",
                name="assistant_outcome",
                native_enum=False,
                create_constraint=True,
                length=40,
            ),
            nullable=False,
        ),
        sa.Column("red_flags", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("cited_event_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("redactions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("escalation_id", sa.Uuid(), nullable=True),
        sa.Column("model", sa.String(length=64), nullable=True),
        sa.Column("prompt_version", sa.String(length=32), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["appointment_id"],
            ["appointment.id"],
            name=op.f("fk_assistant_exchange_appointment_id_appointment"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["escalation_id"],
            ["escalation.id"],
            name=op.f("fk_assistant_exchange_escalation_id_escalation"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
            name=op.f("fk_assistant_exchange_organization_id_organization"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["patient_id"],
            ["patient.id"],
            name=op.f("fk_assistant_exchange_patient_id_patient"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assistant_exchange")),
    )
    op.create_index(
        op.f("ix_assistant_exchange_appointment_id"),
        "assistant_exchange",
        ["appointment_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_assistant_exchange_organization_id"),
        "assistant_exchange",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_assistant_exchange_outcome"), "assistant_exchange", ["outcome"], unique=False
    )
    op.create_index(
        op.f("ix_assistant_exchange_patient_id"), "assistant_exchange", ["patient_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_assistant_exchange_patient_id"), table_name="assistant_exchange")
    op.drop_index(op.f("ix_assistant_exchange_outcome"), table_name="assistant_exchange")
    op.drop_index(op.f("ix_assistant_exchange_organization_id"), table_name="assistant_exchange")
    op.drop_index(op.f("ix_assistant_exchange_appointment_id"), table_name="assistant_exchange")
    op.drop_table("assistant_exchange")
