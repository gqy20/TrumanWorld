"""Add persisted Agent movement state.

Revision ID: 20260801_000001
Revises: 20260321_000004
Create Date: 2026-08-01

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260801_000001"
down_revision = "20260321_000004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column("movement", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )


def downgrade() -> None:
    op.drop_column("agents", "movement")
