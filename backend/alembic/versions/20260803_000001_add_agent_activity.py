"""Add persisted Agent activity state.

Revision ID: 20260803_000001
Revises: 20260802_000004
Create Date: 2026-08-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260803_000001"
down_revision = "20260802_000004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column("activity", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )


def downgrade() -> None:
    op.drop_column("agents", "activity")
