"""Improve director directive execution tracking.

Revision ID: 20260802_000003
Revises: 20260802_000002
Create Date: 2026-08-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260802_000003"
down_revision = "20260802_000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "director_directives", sa.Column("source_memory_id", sa.String(length=64), nullable=True)
    )
    op.add_column(
        "director_directives",
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "director_directives", sa.Column("last_attempt_tick", sa.Integer(), nullable=True)
    )
    op.add_column(
        "director_directives", sa.Column("last_progress_tick", sa.Integer(), nullable=True)
    )
    op.add_column(
        "director_directives",
        sa.Column("last_result_action_type", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "director_directives",
        sa.Column("last_result_target_agent_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "director_directives",
        sa.Column("replaced_by_directive_id", sa.String(length=64), nullable=True),
    )
    op.create_foreign_key(
        "fk_director_directives_source_memory",
        "director_directives",
        "director_memories",
        ["source_memory_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_director_directives_replacement",
        "director_directives",
        "director_directives",
        ["replaced_by_directive_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_director_directives_replacement", "director_directives", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_director_directives_source_memory", "director_directives", type_="foreignkey"
    )
    for column in (
        "replaced_by_directive_id",
        "last_result_target_agent_id",
        "last_result_action_type",
        "last_progress_tick",
        "last_attempt_tick",
        "attempt_count",
        "source_memory_id",
    ):
        op.drop_column("director_directives", column)
