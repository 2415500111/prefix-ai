"""Cache of machine translations of approved prep steps (protocol content, no PHI).

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-28 00:35:22.800886
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "prep_step_translation",
        sa.Column("step_id", sa.Uuid(), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("instruction_text", sa.Text(), nullable=False),
        sa.Column("translated_by", sa.String(length=64), nullable=False),
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
            ["organization_id"],
            ["organization.id"],
            name=op.f("fk_prep_step_translation_organization_id_organization"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["step_id"],
            ["prep_step.id"],
            name=op.f("fk_prep_step_translation_step_id_prep_step"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_prep_step_translation")),
        sa.UniqueConstraint(
            "step_id", "language", name=op.f("uq_prep_step_translation_step_id_language")
        ),
    )
    op.create_index(
        op.f("ix_prep_step_translation_organization_id"),
        "prep_step_translation",
        ["organization_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_prep_step_translation_organization_id"), table_name="prep_step_translation"
    )
    op.drop_table("prep_step_translation")
