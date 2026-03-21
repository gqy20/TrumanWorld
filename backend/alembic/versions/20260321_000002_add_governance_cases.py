"""Add governance_cases and governance_restrictions tables.

Revision ID: 20260321_000002
Revises: 20260321_000001
Create Date: 2026-03-21

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "20260321_000002"
down_revision = "20260321_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create governance_cases table
    op.create_table(
        "governance_cases",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("simulation_runs.id"), nullable=False),
        sa.Column("agent_id", sa.String(64), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("status", sa.String(30), default="open"),
        sa.Column("opened_tick", sa.Integer, default=0),
        sa.Column("last_updated_tick", sa.Integer, default=0),
        sa.Column("primary_reason", sa.String(255), nullable=False),
        sa.Column("severity", sa.String(20), default="low"),
        sa.Column("record_count", sa.Integer, default=0),
        sa.Column("active_restriction_count", sa.Integer, default=0),
        sa.Column("metadata", sa.JSON, default=dict),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("ix_governance_cases_run_id", "governance_cases", ["run_id"])
    op.create_index("ix_governance_cases_run_id_agent_id", "governance_cases", ["run_id", "agent_id"])
    op.create_index(
        "ix_governance_cases_run_id_agent_id_status",
        "governance_cases",
        ["run_id", "agent_id", "status"],
    )

    # Create governance_restrictions table
    op.create_table(
        "governance_restrictions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("simulation_runs.id"), nullable=False),
        sa.Column("agent_id", sa.String(64), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("case_id", sa.String(64), sa.ForeignKey("governance_cases.id"), nullable=True),
        sa.Column("restriction_type", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), default="active"),
        sa.Column("scope_type", sa.String(20), default="action"),
        sa.Column("scope_value", sa.String(100), nullable=True),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column("start_tick", sa.Integer, default=0),
        sa.Column("end_tick", sa.Integer, nullable=True),
        sa.Column("severity", sa.String(20), default="low"),
        sa.Column("metadata", sa.JSON, default=dict),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("ix_governance_restrictions_run_id", "governance_restrictions", ["run_id"])
    op.create_index(
        "ix_governance_restrictions_run_id_agent_id",
        "governance_restrictions",
        ["run_id", "agent_id"],
    )
    op.create_index(
        "ix_governance_restrictions_agent_active",
        "governance_restrictions",
        ["agent_id", "status"],
    )


def downgrade() -> None:
    op.drop_table("governance_restrictions")
    op.drop_table("governance_cases")
