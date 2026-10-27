"""Idempotent reminder dispatch.

Adds the SENDING status; allows one outbound message and one check-in per timeline event;
allows one active (non-cancelled) event per appointment step.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-27 23:55:22.385817
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_STATUS_CHECK = "ck_patient_timeline_event_timeline_event_status"
_NEW_STATUSES = (
    "'PENDING', 'SENDING', 'SENT', 'CONFIRMED', 'MISSED', 'SKIPPED', 'CANCELLED', 'FAILED'"
)
_OLD_STATUSES = "'PENDING', 'SENT', 'CONFIRMED', 'MISSED', 'SKIPPED', 'CANCELLED', 'FAILED'"


def _replace_status_check(values: str) -> None:
    op.drop_constraint(op.f(_STATUS_CHECK), "patient_timeline_event", type_="check")
    op.create_check_constraint(
        op.f(_STATUS_CHECK), "patient_timeline_event", f"status IN ({values})"
    )


def upgrade() -> None:
    _replace_status_check(_NEW_STATUSES)
    op.drop_constraint(
        op.f("uq_patient_timeline_event_appointment_id_step_id"),
        "patient_timeline_event",
        type_="unique",
    )
    op.create_index(
        "uq_patient_timeline_event_active_step",
        "patient_timeline_event",
        ["appointment_id", "step_id"],
        unique=True,
        postgresql_where=sa.text("status <> 'CANCELLED'"),
    )
    op.create_index(
        "uq_check_in_timeline_event",
        "check_in",
        ["timeline_event_id"],
        unique=True,
        postgresql_where=sa.text("timeline_event_id IS NOT NULL"),
    )
    op.create_index(
        "uq_message_outbound_timeline_event",
        "message",
        ["timeline_event_id"],
        unique=True,
        postgresql_where=sa.text("direction = 'OUTBOUND' AND timeline_event_id IS NOT NULL"),
    )
    op.add_column(
        "patient_timeline_event", sa.Column("last_error", sa.String(length=500), nullable=True)
    )


def downgrade() -> None:
    op.execute("UPDATE patient_timeline_event SET status = 'PENDING' WHERE status = 'SENDING'")
    _replace_status_check(_OLD_STATUSES)
    op.drop_index("uq_patient_timeline_event_active_step", table_name="patient_timeline_event")
    op.execute("DELETE FROM patient_timeline_event WHERE status = 'CANCELLED'")
    op.create_unique_constraint(
        op.f("uq_patient_timeline_event_appointment_id_step_id"),
        "patient_timeline_event",
        ["appointment_id", "step_id"],
    )
    op.drop_column("patient_timeline_event", "last_error")
    op.drop_index(
        "uq_message_outbound_timeline_event",
        table_name="message",
        postgresql_where=sa.text("direction = 'OUTBOUND' AND timeline_event_id IS NOT NULL"),
    )
    op.drop_index(
        "uq_check_in_timeline_event",
        table_name="check_in",
        postgresql_where=sa.text("timeline_event_id IS NOT NULL"),
    )
