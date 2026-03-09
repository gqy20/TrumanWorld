from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.protocol.simulation import EventType


class StatusResponse(BaseModel):
    run_id: str
    status: str


class RunDetailResponse(BaseModel):
    id: str
    name: str
    status: str
    scenario_type: str
    current_tick: int
    tick_minutes: int


class TimelineEventResponse(BaseModel):
    id: str
    tick_no: int
    event_type: EventType
    importance: float | None = None
    payload: dict = Field(default_factory=dict)
    world_time: str | None = None  # 该 tick 对应的模拟世界时间，格式 HH:MM
    world_date: str | None = None  # 该 tick 对应的模拟世界日期，格式 YYYY-MM-DD


class WorldEventsResponse(BaseModel):
    run_id: str
    events: list[WorldEventResponse]
    total: int


class TimelineRunInfo(BaseModel):
    current_tick: int
    tick_minutes: int
    world_start_iso: str  # world_start_time ISO 字符串
    current_world_time_iso: str  # 当前 tick 对应的世界时间 ISO


class TimelineResponse(BaseModel):
    run_id: str
    events: list[TimelineEventResponse]
    total: int = 0
    filtered: int = 0
    run_info: TimelineRunInfo | None = None


class DirectorObservationResponse(BaseModel):
    run_id: str
    current_tick: int
    truman_agent_id: str | None = None
    truman_suspicion_score: float
    suspicion_level: str
    continuity_risk: str
    focus_agent_ids: list[str]
    notes: list[str]


class AgentSummaryResponse(BaseModel):
    id: str
    name: str
    occupation: str | None = None
    current_goal: str | None = None
    current_location_id: str | None = None
    config_id: str | None = None


class AgentsListResponse(BaseModel):
    run_id: str
    agents: list[AgentSummaryResponse]


class AgentEventResponse(BaseModel):
    id: str
    tick_no: int
    event_type: EventType
    actor_agent_id: str | None = None
    actor_name: str | None = None
    target_agent_id: str | None = None
    target_name: str | None = None
    location_id: str | None = None
    location_name: str | None = None
    payload: dict = Field(default_factory=dict)


class AgentMemoryResponse(BaseModel):
    id: str
    memory_type: str
    summary: str | None = None
    content: str
    importance: float | None = None
    related_agent_id: str | None = None
    related_agent_name: str | None = None


class AgentRelationshipResponse(BaseModel):
    other_agent_id: str
    other_agent_name: str | None = None
    familiarity: float
    trust: float
    affinity: float
    relation_type: str


class AgentDetailResponse(BaseModel):
    run_id: str
    agent_id: str
    name: str
    occupation: str | None = None
    status: dict = Field(default_factory=dict)
    current_goal: str | None = None
    config_id: str | None = None
    personality: dict = Field(default_factory=dict)
    profile: dict = Field(default_factory=dict)
    recent_events: list[AgentEventResponse]
    memories: list[AgentMemoryResponse]
    relationships: list[AgentRelationshipResponse]


class WorldClockResponse(BaseModel):
    iso: str
    date: str
    time: str
    year: int
    month: int
    day: int
    hour: int
    minute: int
    weekday: int
    weekday_name: str
    weekday_name_cn: str
    is_weekend: bool
    time_period: str
    time_period_cn: str


class WorldLocationResponse(BaseModel):
    id: str
    name: str
    location_type: str
    x: int
    y: int
    capacity: int
    occupants: list[AgentSummaryResponse]


class WorldEventResponse(BaseModel):
    id: str
    tick_no: int
    event_type: EventType
    location_id: str | None = None
    actor_agent_id: str | None = None
    target_agent_id: str | None = None
    actor_name: str | None = None
    target_name: str | None = None
    location_name: str | None = None
    payload: dict = Field(default_factory=dict)


class WorldSnapshotRunResponse(BaseModel):
    id: str
    name: str
    status: str
    scenario_type: str
    current_tick: int
    tick_minutes: int
    started_at: datetime | None = None
    elapsed_seconds: int = 0


class WorldDirectorStatsResponse(BaseModel):
    total: int = 0
    executed: int = 0
    execution_rate: int = 0


class WorldDailyStatsResponse(BaseModel):
    talk_count: int = 0
    move_count: int = 0
    rejection_count: int = 0


class WorldHealthMetricsConfig(BaseModel):
    """Health metrics evaluation baselines, loaded from world_config.yml."""
    # Continuity score
    continuity_penalty_factor: float = 200.0
    continuity_warning_threshold: float = 0.2
    continuity_trend_down_threshold: float = 0.15
    continuity_trend_stable_threshold: float = 0.05
    # Social activity score
    social_baseline_talks_per_person_per_day: float = 20.0
    social_trend_up_threshold: float = 10.0
    social_trend_stable_threshold: float = 3.0


class DirectorMemoryResponse(BaseModel):
    id: str
    tick_no: int
    scene_goal: str
    priority: str
    urgency: str
    message_hint: str | None = None
    target_agent_id: str | None = None
    target_agent_name: str | None = None
    target_cast_ids: list[str] = Field(default_factory=list)
    target_cast_names: list[str] = Field(default_factory=list)
    location_hint: str | None = None
    location_name: str | None = None
    reason: str | None = None
    was_executed: bool
    delivery_status: str
    effectiveness_score: float | None = None
    trigger_suspicion_score: float = 0.0
    trigger_continuity_risk: str = "stable"
    cooldown_ticks: int = 0
    cooldown_until_tick: int | None = None
    created_at: datetime


class DirectorMemoriesResponse(BaseModel):
    run_id: str
    memories: list[DirectorMemoryResponse]
    total: int = 0


class WorldSnapshotResponse(BaseModel):
    run: WorldSnapshotRunResponse
    world_clock: WorldClockResponse
    locations: list[WorldLocationResponse]
    recent_events: list[WorldEventResponse]
    director_stats: WorldDirectorStatsResponse = Field(default_factory=WorldDirectorStatsResponse)
    daily_stats: WorldDailyStatsResponse = Field(default_factory=WorldDailyStatsResponse)
    health_metrics_config: WorldHealthMetricsConfig = Field(default_factory=WorldHealthMetricsConfig)
