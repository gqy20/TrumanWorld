"""Separate director execution from delayed effect evaluation.

Revision ID: 20260802_000004
Revises: 20260802_000003
Create Date: 2026-08-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260802_000004"
down_revision = "20260802_000003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "director_directives",
        sa.Column("effect_status", sa.String(length=20), nullable=False, server_default="pending"),
    )
    op.add_column(
        "director_directives", sa.Column("effectiveness_score", sa.Float(), nullable=True)
    )
    op.add_column("director_directives", sa.Column("evaluated_tick", sa.Integer(), nullable=True))
    op.execute(
        "UPDATE director_directives SET effect_status = 'evaluated', "
        "effectiveness_score = 1.0, evaluated_tick = completed_tick "
        "WHERE status = 'succeeded'"
    )


def downgrade() -> None:
    op.drop_column("director_directives", "evaluated_tick")
    op.drop_column("director_directives", "effectiveness_score")
    op.drop_column("director_directives", "effect_status")
