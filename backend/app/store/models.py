from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db import Base


class SimulationRun(Base):
    __tablename__ = "simulation_runs"
    __table_args__ = (Index("ix_simulation_runs_status", "status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="draft")
    current_tick: Mapped[int] = mapped_column(Integer, default=0)
    tick_minutes: Mapped[int] = mapped_column(Integer, default=5)
    world_seed: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class Agent(Base):
    __tablename__ = "agents"
    __table_args__ = (
        Index("ix_agents_run_id", "run_id"),
        Index("ix_agents_run_id_name", "run_id", "name"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("simulation_runs.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    occupation: Mapped[str | None] = mapped_column(String(100))
    home_location_id: Mapped[str | None] = mapped_column(ForeignKey("locations.id"))
    current_location_id: Mapped[str | None] = mapped_column(ForeignKey("locations.id"))
    current_goal: Mapped[str | None] = mapped_column(String(255))
    personality: Mapped[dict] = mapped_column(JSON, default=dict)
    profile: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[dict] = mapped_column(JSON, default=dict)
    current_plan: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class Location(Base):
    __tablename__ = "locations"
    __table_args__ = (Index("ix_locations_run_id", "run_id"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("simulation_runs.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    location_type: Mapped[str] = mapped_column(String(50))
    x: Mapped[int] = mapped_column(Integer, default=0)
    y: Mapped[int] = mapped_column(Integer, default=0)
    capacity: Mapped[int] = mapped_column(Integer, default=10)
    attributes: Mapped[dict] = mapped_column(JSON, default=dict)


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        Index("ix_events_run_id_tick_no", "run_id", "tick_no"),
        Index("ix_events_run_id_event_type", "run_id", "event_type"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("simulation_runs.id"), nullable=False)
    tick_no: Mapped[int] = mapped_column(Integer, default=0)
    world_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_agent_id: Mapped[str | None] = mapped_column(ForeignKey("agents.id"))
    target_agent_id: Mapped[str | None] = mapped_column(ForeignKey("agents.id"))
    location_id: Mapped[str | None] = mapped_column(ForeignKey("locations.id"))
    importance: Mapped[float] = mapped_column(Float, default=0.0)
    visibility: Mapped[str] = mapped_column(String(30), default="public")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Relationship(Base):
    __tablename__ = "relationships"
    __table_args__ = (
        Index("ix_relationships_run_id_agent_id", "run_id", "agent_id"),
        Index("ix_relationships_pair", "run_id", "agent_id", "other_agent_id", unique=True),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("simulation_runs.id"), nullable=False)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False)
    other_agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False)
    familiarity: Mapped[float] = mapped_column(Float, default=0.0)
    trust: Mapped[float] = mapped_column(Float, default=0.0)
    affinity: Mapped[float] = mapped_column(Float, default=0.0)
    relation_type: Mapped[str] = mapped_column(String(30), default="stranger")
    last_interaction_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class Memory(Base):
    __tablename__ = "memories"
    __table_args__ = (
        Index("ix_memories_agent_id_created_at", "agent_id", "created_at"),
        Index("ix_memories_run_id_memory_type", "run_id", "memory_type"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("simulation_runs.id"), nullable=False)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False)
    tick_no: Mapped[int] = mapped_column(Integer, default=0)
    memory_type: Mapped[str] = mapped_column(String(30), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(String(500))
    importance: Mapped[float] = mapped_column(Float, default=0.0)
    emotional_valence: Mapped[float] = mapped_column(Float, default=0.0)
    related_agent_id: Mapped[str | None] = mapped_column(ForeignKey("agents.id"))
    location_id: Mapped[str | None] = mapped_column(ForeignKey("locations.id"))
    source_event_id: Mapped[str | None] = mapped_column(ForeignKey("events.id"))
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
