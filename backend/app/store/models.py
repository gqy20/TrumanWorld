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
    scenario_type: Mapped[str] = mapped_column(String(30), default="truman_world")
    current_tick: Mapped[int] = mapped_column(Integer, default=0)
    tick_minutes: Mapped[int] = mapped_column(Integer, default=5)
    world_seed: Mapped[int | None] = mapped_column(Integer)
    # 标记服务重启前是否在运行中，用于一键恢复
    was_running_before_restart: Mapped[bool] = mapped_column(default=False)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    elapsed_seconds: Mapped[int] = mapped_column(Integer, default=0)
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
        Index("ix_memories_agent_id_category", "agent_id", "memory_category"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("simulation_runs.id"), nullable=False)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False)
    tick_no: Mapped[int] = mapped_column(Integer, default=0)
    memory_type: Mapped[str] = mapped_column(String(30), nullable=False)
    memory_category: Mapped[str] = mapped_column(String(20), default="short_term")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(String(500))
    importance: Mapped[float] = mapped_column(Float, default=0.0)
    event_importance: Mapped[float] = mapped_column(Float, default=0.0)
    self_relevance: Mapped[float] = mapped_column(Float, default=0.0)
    belief_confidence: Mapped[float] = mapped_column(Float, default=1.0)
    emotional_valence: Mapped[float] = mapped_column(Float, default=0.0)
    streak_count: Mapped[int] = mapped_column(Integer, default=1)
    last_tick_no: Mapped[int | None] = mapped_column(Integer)
    retrieval_count: Mapped[int] = mapped_column(Integer, default=0)
    last_accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    related_agent_id: Mapped[str | None] = mapped_column(ForeignKey("agents.id"))
    location_id: Mapped[str | None] = mapped_column(ForeignKey("locations.id"))
    source_event_id: Mapped[str | None] = mapped_column(ForeignKey("events.id"))
    consolidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LlmCall(Base):
    """LLM 调用记录 - 统计 token 消耗和费用"""

    __tablename__ = "llm_calls"
    __table_args__ = (
        Index("ix_llm_calls_run_id", "run_id"),
        Index("ix_llm_calls_run_id_agent_id", "run_id", "agent_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("simulation_runs.id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[str | None] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"), nullable=True
    )
    task_type: Mapped[str] = mapped_column(String(30), nullable=False)  # planner/reactor/reflector
    tick_no: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_read_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_creation_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DirectorMemory(Base):
    """导演干预记忆 - 记录导演的决策历史和干预效果"""

    __tablename__ = "director_memories"
    __table_args__ = (
        Index("ix_director_memories_run_id_tick_no", "run_id", "tick_no"),
        Index("ix_director_memories_run_id_scene_goal", "run_id", "scene_goal"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("simulation_runs.id"), nullable=False)
    tick_no: Mapped[int] = mapped_column(Integer, default=0)
    # 场景目标
    scene_goal: Mapped[str] = mapped_column(String(50), nullable=False)
    # 目标 cast agent
    target_cast_ids: Mapped[str] = mapped_column(Text, nullable=False)  # JSON array
    # 干预优先级
    priority: Mapped[str] = mapped_column(String(20), default="advisory")
    urgency: Mapped[str] = mapped_column(String(20), default="advisory")
    # 干预内容
    message_hint: Mapped[str | None] = mapped_column(Text)
    target_agent_id: Mapped[str | None] = mapped_column(String(64))
    reason: Mapped[str | None] = mapped_column(Text)
    # 效果追踪
    was_executed: Mapped[bool] = mapped_column(default=False)
    effectiveness_score: Mapped[float | None] = mapped_column(Float)
    # 触发时的世界状态快照
    trigger_suspicion_score: Mapped[float] = mapped_column(Float, default=0.0)
    trigger_continuity_risk: Mapped[str] = mapped_column(String(20), default="stable")
    # 冷却信息
    cooldown_ticks: Mapped[int] = mapped_column(Integer, default=3)
    cooldown_until_tick: Mapped[int | None] = mapped_column(Integer)
    # 元数据
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
