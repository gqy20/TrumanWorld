"""Expand LLM call observability fields.

Revision ID: 20260802_000001
Revises: 20260801_000001
Create Date: 2026-08-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260802_000001"
down_revision = "20260801_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("llm_calls", sa.Column("backend", sa.String(length=30), nullable=True))
    op.add_column(
        "llm_calls",
        sa.Column("status", sa.String(length=30), nullable=False, server_default="success"),
    )
    op.add_column("llm_calls", sa.Column("trace_id", sa.String(length=64), nullable=True))
    op.add_column("llm_calls", sa.Column("node_name", sa.String(length=100), nullable=True))
    op.add_column(
        "llm_calls",
        sa.Column("attempt_no", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column("llm_calls", sa.Column("exception_type", sa.String(length=100), nullable=True))
    op.add_column("llm_calls", sa.Column("failure_reason", sa.String(length=100), nullable=True))
    op.add_column("llm_calls", sa.Column("fallback_from", sa.String(length=50), nullable=True))
    op.create_index("ix_llm_calls_run_id_trace_id", "llm_calls", ["run_id", "trace_id"])


def downgrade() -> None:
    op.drop_index("ix_llm_calls_run_id_trace_id", table_name="llm_calls")
    op.drop_column("llm_calls", "fallback_from")
    op.drop_column("llm_calls", "failure_reason")
    op.drop_column("llm_calls", "exception_type")
    op.drop_column("llm_calls", "attempt_no")
    op.drop_column("llm_calls", "node_name")
    op.drop_column("llm_calls", "trace_id")
    op.drop_column("llm_calls", "status")
    op.drop_column("llm_calls", "backend")
