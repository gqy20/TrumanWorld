"""initial schema

Revision ID: 20260307_000001
Revises:
Create Date: 2026-03-07 13:10:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260307_000001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "simulation_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="draft"),
        sa.Column("current_tick", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tick_minutes", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("world_seed", sa.Integer(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_simulation_runs_status", "simulation_runs", ["status"])

    op.create_table(
        "locations",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column(
            "run_id", sa.String(length=36), sa.ForeignKey("simulation_runs.id"), nullable=False
        ),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("location_type", sa.String(length=50), nullable=False),
        sa.Column("x", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("y", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("capacity", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("attributes", sa.JSON(), nullable=False),
    )
    op.create_index("ix_locations_run_id", "locations", ["run_id"])

    op.create_table(
        "agents",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column(
            "run_id", sa.String(length=36), sa.ForeignKey("simulation_runs.id"), nullable=False
        ),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("occupation", sa.String(length=100), nullable=True),
        sa.Column(
            "home_location_id", sa.String(length=64), sa.ForeignKey("locations.id"), nullable=True
        ),
        sa.Column(
            "current_location_id",
            sa.String(length=64),
            sa.ForeignKey("locations.id"),
            nullable=True,
        ),
        sa.Column("current_goal", sa.String(length=255), nullable=True),
        sa.Column("personality", sa.JSON(), nullable=False),
        sa.Column("profile", sa.JSON(), nullable=False),
        sa.Column("status", sa.JSON(), nullable=False),
        sa.Column("current_plan", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_agents_run_id", "agents", ["run_id"])
    op.create_index("ix_agents_run_id_name", "agents", ["run_id", "name"])

    op.create_table(
        "events",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column(
            "run_id", sa.String(length=36), sa.ForeignKey("simulation_runs.id"), nullable=False
        ),
        sa.Column("tick_no", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("world_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column(
            "actor_agent_id", sa.String(length=64), sa.ForeignKey("agents.id"), nullable=True
        ),
        sa.Column(
            "target_agent_id", sa.String(length=64), sa.ForeignKey("agents.id"), nullable=True
        ),
        sa.Column(
            "location_id", sa.String(length=64), sa.ForeignKey("locations.id"), nullable=True
        ),
        sa.Column("importance", sa.Float(), nullable=False, server_default="0"),
        sa.Column("visibility", sa.String(length=30), nullable=False, server_default="public"),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_events_run_id_tick_no", "events", ["run_id", "tick_no"])
    op.create_index("ix_events_run_id_event_type", "events", ["run_id", "event_type"])

    op.create_table(
        "relationships",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column(
            "run_id", sa.String(length=36), sa.ForeignKey("simulation_runs.id"), nullable=False
        ),
        sa.Column("agent_id", sa.String(length=64), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column(
            "other_agent_id", sa.String(length=64), sa.ForeignKey("agents.id"), nullable=False
        ),
        sa.Column("familiarity", sa.Float(), nullable=False, server_default="0"),
        sa.Column("trust", sa.Float(), nullable=False, server_default="0"),
        sa.Column("affinity", sa.Float(), nullable=False, server_default="0"),
        sa.Column("relation_type", sa.String(length=30), nullable=False, server_default="stranger"),
        sa.Column("last_interaction_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_relationships_run_id_agent_id", "relationships", ["run_id", "agent_id"])
    op.create_index(
        "ix_relationships_pair",
        "relationships",
        ["run_id", "agent_id", "other_agent_id"],
        unique=True,
    )

    op.create_table(
        "memories",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column(
            "run_id", sa.String(length=36), sa.ForeignKey("simulation_runs.id"), nullable=False
        ),
        sa.Column("agent_id", sa.String(length=64), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("tick_no", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("memory_type", sa.String(length=30), nullable=False),
        sa.Column(
            "memory_category", sa.String(length=20), nullable=False, server_default="short_term"
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=True),
        sa.Column("importance", sa.Float(), nullable=False, server_default="0"),
        sa.Column("event_importance", sa.Float(), nullable=False, server_default="0"),
        sa.Column("self_relevance", sa.Float(), nullable=False, server_default="0"),
        sa.Column("belief_confidence", sa.Float(), nullable=False, server_default="1"),
        sa.Column("emotional_valence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("streak_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("last_tick_no", sa.Integer(), nullable=True),
        sa.Column("retrieval_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "related_agent_id", sa.String(length=64), sa.ForeignKey("agents.id"), nullable=True
        ),
        sa.Column(
            "location_id", sa.String(length=64), sa.ForeignKey("locations.id"), nullable=True
        ),
        sa.Column(
            "source_event_id", sa.String(length=64), sa.ForeignKey("events.id"), nullable=True
        ),
        sa.Column("consolidated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_memories_agent_id_created_at", "memories", ["agent_id", "created_at"])
    op.create_index("ix_memories_run_id_memory_type", "memories", ["run_id", "memory_type"])
    op.create_index("ix_memories_agent_id_category", "memories", ["agent_id", "memory_category"])


def downgrade() -> None:
    op.drop_index("ix_memories_agent_id_category", table_name="memories")
    op.drop_index("ix_memories_run_id_memory_type", table_name="memories")
    op.drop_index("ix_memories_agent_id_created_at", table_name="memories")
    op.drop_table("memories")

    op.drop_index("ix_relationships_pair", table_name="relationships")
    op.drop_index("ix_relationships_run_id_agent_id", table_name="relationships")
    op.drop_table("relationships")

    op.drop_index("ix_events_run_id_event_type", table_name="events")
    op.drop_index("ix_events_run_id_tick_no", table_name="events")
    op.drop_table("events")

    op.drop_index("ix_agents_run_id_name", table_name="agents")
    op.drop_index("ix_agents_run_id", table_name="agents")
    op.drop_table("agents")

    op.drop_index("ix_locations_run_id", table_name="locations")
    op.drop_table("locations")

    op.drop_index("ix_simulation_runs_status", table_name="simulation_runs")
    op.drop_table("simulation_runs")
