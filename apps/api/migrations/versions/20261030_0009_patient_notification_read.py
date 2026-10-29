"""Patient portal updates: which items a patient has read.

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-30 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "patient_notification_read",
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
            name=op.f("fk_patient_notification_read_organization_id_organization"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["patient_id"],
            ["patient.id"],
            name=op.f("fk_patient_notification_read_patient_id_patient"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_patient_notification_read")),
        sa.UniqueConstraint(
            "patient_id", "key", name=op.f("uq_patient_notification_read_patient_id_key")
        ),
    )
    op.create_index(
        op.f("ix_patient_notification_read_organization_id"),
        "patient_notification_read",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_patient_notification_read_patient_id"),
        "patient_notification_read",
        ["patient_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_patient_notification_read_patient_id"), table_name="patient_notification_read"
    )
    op.drop_index(
        op.f("ix_patient_notification_read_organization_id"),
        table_name="patient_notification_read",
    )
    op.drop_table("patient_notification_read")
