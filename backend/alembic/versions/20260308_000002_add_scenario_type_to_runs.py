"""add scenario_type to simulation_runs

Revision ID: 20260308_000002
Revises: 20260308_000001
Create Date: 2026-03-08

"""

from alembic import op
import sqlalchemy as sa


revision = "20260308_000002"
down_revision = "20260308_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "simulation_runs",
        sa.Column(
            "scenario_type",
            sa.String(length=30),
            nullable=False,
            server_default="narrative_world",
        ),
    )
    op.execute(
        "UPDATE simulation_runs SET scenario_type = 'narrative_world' WHERE scenario_type IS NULL"
    )
    op.alter_column("simulation_runs", "scenario_type", server_default=None)


def downgrade() -> None:
    op.drop_column("simulation_runs", "scenario_type")
