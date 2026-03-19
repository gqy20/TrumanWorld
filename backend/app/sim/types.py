from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypedDict

from app.scenario.types import AgentProfile, ScenarioGuidance


@dataclass
class AgentDecisionSnapshot:
    id: str
    current_goal: str | None
    current_location_id: str
    home_location_id: str | None
    profile: AgentProfile
    recent_events: list[dict[str, Any]]
    # 预加载的记忆缓存，用于 MCP 工具查询（避免在 anyio task 中创建 DB session）
    memory_cache: dict[str, list[dict[str, Any]]] | None = None
    # Agent 的日程计划，用于传递给 LLM 做上下文感知决策
    current_plan: dict[str, Any] | None = None


class NearbyAgentContext(TypedDict):
    id: str
    name: str
    occupation: str | None


class RuntimeWorldContext(ScenarioGuidance, total=False):
    current_goal: str
    current_location_id: str
    current_location_name: str
    current_location_type: str
    known_location_ids: list[str]
    home_location_id: str
    nearby_agent_id: str
    nearby_agent: NearbyAgentContext
    self_status: dict[str, Any]
    subject_alert_score: float
    world_role: str
    tick_no: int
    tick_minutes: int
    world_time: str
    daily_schedule: dict[str, str]
