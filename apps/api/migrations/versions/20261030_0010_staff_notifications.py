"""Staff notifications: what patients raised, newest first, with per-person read marks.

Also indexes the nurse inbox and the reschedule requests for newest-first listing.

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-30 17:34:11.928641
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "staff_notification",
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("appointment_id", sa.Uuid(), nullable=True),
        sa.Column("escalation_id", sa.Uuid(), nullable=True),
        sa.Column("task_id", sa.Uuid(), nullable=True),
        sa.Column(
            "kind",
            sa.Enum(
                "PROBLEM",
                "QUESTION",
                "HELP",
                "MESSAGE",
                "RESCHEDULE",
                name="staff_notification_kind",
                native_enum=False,
                create_constraint=True,
                length=40,
            ),
            nullable=False,
        ),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("red_flag", sa.Boolean(), nullable=False),
        sa.Column("critical_step", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["appointment_id"],
            ["appointment.id"],
            name=op.f("fk_staff_notification_appointment_id_appointment"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["escalation_id"],
            ["escalation.id"],
            name=op.f("fk_staff_notification_escalation_id_escalation"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
            name=op.f("fk_staff_notification_organization_id_organization"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["patient_id"],
            ["patient.id"],
            name=op.f("fk_staff_notification_patient_id_patient"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["task.id"],
            name=op.f("fk_staff_notification_task_id_task"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_staff_notification")),
    )
    op.create_index(
        op.f("ix_staff_notification_appointment_id"),
        "staff_notification",
        ["appointment_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_staff_notification_escalation_id"),
        "staff_notification",
        ["escalation_id"],
        unique=False,
    )
    op.create_index(
        "ix_staff_notification_newest",
        "staff_notification",
        ["organization_id", "created_at", "id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_staff_notification_organization_id"),
        "staff_notification",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_staff_notification_patient_id"), "staff_notification", ["patient_id"], unique=False
    )
    op.create_index(
        op.f("ix_staff_notification_task_id"), "staff_notification", ["task_id"], unique=False
    )
    op.create_table(
        "staff_notification_read",
        sa.Column("notification_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["notification_id"],
            ["staff_notification.id"],
            name=op.f("fk_staff_notification_read_notification_id_staff_notification"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
            name=op.f("fk_staff_notification_read_organization_id_organization"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name=op.f("fk_staff_notification_read_user_id_app_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_staff_notification_read")),
        sa.UniqueConstraint(
            "notification_id",
            "user_id",
            name=op.f("uq_staff_notification_read_notification_id_user_id"),
        ),
    )
    op.create_index(
        op.f("ix_staff_notification_read_notification_id"),
        "staff_notification_read",
        ["notification_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_staff_notification_read_organization_id"),
        "staff_notification_read",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_staff_notification_read_user_id"),
        "staff_notification_read",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_escalation_newest", "escalation", ["organization_id", "created_at", "id"], unique=False
    )
    op.create_index(
        "ix_task_newest", "task", ["organization_id", "type", "created_at", "id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_task_newest", table_name="task")
    op.drop_index("ix_escalation_newest", table_name="escalation")
    op.drop_index(op.f("ix_staff_notification_read_user_id"), table_name="staff_notification_read")
    op.drop_index(
        op.f("ix_staff_notification_read_organization_id"), table_name="staff_notification_read"
    )
    op.drop_index(
        op.f("ix_staff_notification_read_notification_id"), table_name="staff_notification_read"
    )
    op.drop_table("staff_notification_read")
    op.drop_index(op.f("ix_staff_notification_task_id"), table_name="staff_notification")
    op.drop_index(op.f("ix_staff_notification_patient_id"), table_name="staff_notification")
    op.drop_index(op.f("ix_staff_notification_organization_id"), table_name="staff_notification")
    op.drop_index("ix_staff_notification_newest", table_name="staff_notification")
    op.drop_index(op.f("ix_staff_notification_escalation_id"), table_name="staff_notification")
    op.drop_index(op.f("ix_staff_notification_appointment_id"), table_name="staff_notification")
    op.drop_table("staff_notification")
