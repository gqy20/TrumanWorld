"""Add persistent director directives.

Revision ID: 20260802_000002
Revises: 20260802_000001
Create Date: 2026-08-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260802_000002"
down_revision = "20260802_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "director_directives",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("target_agent_id", sa.String(length=64), nullable=False),
        sa.Column("subject_agent_id", sa.String(length=64), nullable=True),
        sa.Column("objective", sa.String(length=100), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("priority", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("issued_tick", sa.Integer(), nullable=False),
        sa.Column("expires_at_tick", sa.Integer(), nullable=False),
        sa.Column("completed_tick", sa.Integer(), nullable=True),
        sa.Column("location_id", sa.String(length=64), nullable=True),
        sa.Column("message_hint", sa.Text(), nullable=True),
        sa.Column("constraints_json", sa.JSON(), nullable=False),
        sa.Column("completion_criteria_json", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False, server_default="auto"),
        sa.Column("disposition", sa.String(length=20), nullable=True),
        sa.Column("failure_reason", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["run_id"], ["simulation_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_agent_id"], ["agents.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_director_directives_run_status", "director_directives", ["run_id", "status"]
    )
    op.create_index(
        "ix_director_directives_run_agent", "director_directives", ["run_id", "target_agent_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_director_directives_run_agent", table_name="director_directives")
    op.drop_index("ix_director_directives_run_status", table_name="director_directives")
    op.drop_table("director_directives")
