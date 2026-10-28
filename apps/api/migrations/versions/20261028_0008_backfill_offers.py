"""Waitlist backfill: one open and one accepted offer per released slot.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-28 15:05:07.245641
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "backfill_offer",
        sa.Column("slot_appointment_id", sa.Uuid(), nullable=False),
        sa.Column("waitlist_entry_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "OPEN",
                "ACCEPTED",
                "DECLINED",
                name="offer_status",
                native_enum=False,
                create_constraint=True,
                length=40,
            ),
            nullable=False,
        ),
        sa.Column("booked_appointment_id", sa.Uuid(), nullable=True),
        sa.Column(
            "reasons",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
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
            ["booked_appointment_id"],
            ["appointment.id"],
            name=op.f("fk_backfill_offer_booked_appointment_id_appointment"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
            name=op.f("fk_backfill_offer_organization_id_organization"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["slot_appointment_id"],
            ["appointment.id"],
            name=op.f("fk_backfill_offer_slot_appointment_id_appointment"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["waitlist_entry_id"],
            ["waitlist_entry.id"],
            name=op.f("fk_backfill_offer_waitlist_entry_id_waitlist_entry"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_backfill_offer")),
    )
    op.create_index(
        op.f("ix_backfill_offer_organization_id"),
        "backfill_offer",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_backfill_offer_slot_appointment_id"),
        "backfill_offer",
        ["slot_appointment_id"],
        unique=False,
    )
    op.create_index(op.f("ix_backfill_offer_status"), "backfill_offer", ["status"], unique=False)
    op.create_index(
        op.f("ix_backfill_offer_waitlist_entry_id"),
        "backfill_offer",
        ["waitlist_entry_id"],
        unique=False,
    )
    op.create_index(
        "uq_backfill_offer_accepted_per_slot",
        "backfill_offer",
        ["slot_appointment_id"],
        unique=True,
        postgresql_where=sa.text("status = 'ACCEPTED'"),
    )
    op.create_index(
        "uq_backfill_offer_open_per_slot",
        "backfill_offer",
        ["slot_appointment_id"],
        unique=True,
        postgresql_where=sa.text("status = 'OPEN'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_backfill_offer_open_per_slot",
        table_name="backfill_offer",
        postgresql_where=sa.text("status = 'OPEN'"),
    )
    op.drop_index(
        "uq_backfill_offer_accepted_per_slot",
        table_name="backfill_offer",
        postgresql_where=sa.text("status = 'ACCEPTED'"),
    )
    op.drop_index(op.f("ix_backfill_offer_waitlist_entry_id"), table_name="backfill_offer")
    op.drop_index(op.f("ix_backfill_offer_status"), table_name="backfill_offer")
    op.drop_index(op.f("ix_backfill_offer_slot_appointment_id"), table_name="backfill_offer")
    op.drop_index(op.f("ix_backfill_offer_organization_id"), table_name="backfill_offer")
    op.drop_table("backfill_offer")
