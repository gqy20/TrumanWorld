"""add memory streak fields

Revision ID: 20260312_000002
Revises: 20260312_000001
Create Date: 2026-03-12 02:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260312_000002"
down_revision = "20260312_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "memories",
        sa.Column("streak_count", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "memories",
        sa.Column("last_tick_no", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("memories", "last_tick_no")
    op.drop_column("memories", "streak_count")
