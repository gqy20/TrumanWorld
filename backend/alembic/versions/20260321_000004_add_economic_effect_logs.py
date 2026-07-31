"""Add economic_effect_logs table.

Revision ID: 20260321_000004
Revises: 20260321_000003
Create Date: 2026-03-21

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "20260321_000004"
down_revision = "20260321_000003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "economic_effect_logs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("simulation_runs.id"), nullable=False),
        sa.Column("agent_id", sa.String(64), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("case_id", sa.String(64), nullable=True),
        sa.Column("tick_no", sa.Integer, default=0),
        sa.Column("effect_type", sa.String(50), nullable=False),
        sa.Column("cash_delta", sa.Float, default=0.0),
        sa.Column("food_security_delta", sa.Float, default=0.0),
        sa.Column("housing_security_delta", sa.Float, default=0.0),
        sa.Column("employment_status_before", sa.String(20), nullable=True),
        sa.Column("employment_status_after", sa.String(20), nullable=True),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column("metadata", sa.JSON, default=dict),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "ix_economic_effect_logs_run_id_agent_id",
        "economic_effect_logs",
        ["run_id", "agent_id"],
    )
    op.create_index(
        "ix_economic_effect_logs_run_id_tick_no",
        "economic_effect_logs",
        ["run_id", "tick_no"],
    )


def downgrade() -> None:
    op.drop_table("economic_effect_logs")
