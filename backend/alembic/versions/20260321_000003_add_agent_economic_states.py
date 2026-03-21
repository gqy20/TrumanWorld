"""Add agent_economic_states table.

Revision ID: 20260321_000003
Revises: 20260321_000002
Create Date: 2026-03-21

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "20260321_000003"
down_revision = "20260321_000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_economic_states",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("simulation_runs.id"), nullable=False),
        sa.Column("agent_id", sa.String(64), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("cash", sa.Float, default=100.0),
        sa.Column("employment_status", sa.String(20), default="stable"),
        sa.Column("food_security", sa.Float, default=1.0),
        sa.Column("housing_security", sa.Float, default=1.0),
        sa.Column("work_restriction_until_tick", sa.Integer, nullable=True),
        sa.Column("last_income_tick", sa.Integer, nullable=True),
        sa.Column("metadata", sa.JSON, default=dict),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "ix_agent_economic_states_run_id_agent_id",
        "agent_economic_states",
        ["run_id", "agent_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("agent_economic_states")
