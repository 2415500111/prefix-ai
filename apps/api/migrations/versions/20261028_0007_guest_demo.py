"""Guest demo access: the DEMO_VIEWER role and the demo-hospital flag on organisations.

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-28 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ROLE_CHECK = "ck_app_user_role"
_OLD_ROLES = "'ADMIN', 'COORDINATOR', 'NURSE', 'CLINICIAN', 'VIEWER'"
_NEW_ROLES = _OLD_ROLES + ", 'DEMO_VIEWER'"


def _replace_role_check(values: str) -> None:
    op.drop_constraint(op.f(_ROLE_CHECK), "app_user", type_="check")
    op.create_check_constraint(op.f(_ROLE_CHECK), "app_user", f"role IN ({values})")


def upgrade() -> None:
    _replace_role_check(_NEW_ROLES)
    op.add_column(
        "organization",
        sa.Column("is_demo", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("organization", "is_demo")
    op.execute("UPDATE app_user SET role = 'VIEWER' WHERE role = 'DEMO_VIEWER'")
    _replace_role_check(_OLD_ROLES)
