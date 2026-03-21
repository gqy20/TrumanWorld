"""add governance_records table

Revision ID: 20260321_000001
Revises: 20260320_000001
Create Date: 2026-03-21
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260321_000001"
down_revision: str | None = "20260320_000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "governance_records",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("agent_id", sa.String(length=64), nullable=False),
        sa.Column("tick_no", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_event_id", sa.String(length=64), nullable=True),
        sa.Column("location_id", sa.String(length=64), nullable=True),
        sa.Column("action_type", sa.String(length=50), nullable=False),
        sa.Column("decision", sa.String(length=30), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("observed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("observation_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("intervention_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"]),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"]),
        sa.ForeignKeyConstraint(["run_id"], ["simulation_runs.id"]),
        sa.ForeignKeyConstraint(["source_event_id"], ["events.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_governance_records_run_id_tick_no",
        "governance_records",
        ["run_id", "tick_no"],
    )
    op.create_index(
        "ix_governance_records_run_id_agent_id",
        "governance_records",
        ["run_id", "agent_id"],
    )
    op.create_index(
        "ix_governance_records_source_event_id",
        "governance_records",
        ["source_event_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_governance_records_source_event_id", table_name="governance_records")
    op.drop_index("ix_governance_records_run_id_agent_id", table_name="governance_records")
    op.drop_index("ix_governance_records_run_id_tick_no", table_name="governance_records")
    op.drop_table("governance_records")
