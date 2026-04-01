from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.cognition.protocols import LLMCallCallback, MemoryCacheProtocol


@dataclass
class BackendExecutionContext:
    run_id: str | None = None
    enable_memory_tools: bool = True
    on_llm_call: LLMCallCallback = None
    memory_cache: MemoryCacheProtocol | None = None


@dataclass
class AgentActionInvocation:
    agent_id: str
    prompt: str
    context: dict[str, Any]
    max_turns: int
    max_budget_usd: float
    allowed_actions: list[str] = field(default_factory=list)


@dataclass
class PlanningInvocation:
    agent_id: str
    agent_name: str
    prompt: str
    context: dict[str, Any]


@dataclass
class ReflectionInvocation:
    agent_id: str
    agent_name: str
    prompt: str
    context: dict[str, Any]


@dataclass
class DirectorDecisionInvocation:
    prompt: str
    context: dict[str, Any]  # World state context for director
    recent_goals: set[str]


@dataclass
class AgentDecisionResult:
    action_type: str
    target_location_id: str | None = None
    target_agent_id: str | None = None
    message: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    plan_update: dict[str, Any] | None = None  # Optional plan update
    raw_intent: str | None = None  # Original intent description (for free actions)
