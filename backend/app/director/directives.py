from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal
from uuid import uuid4

from app.director.types import DirectorPlan

DirectiveMode = Literal["advisory", "priority", "enforced"]
DirectiveStatus = Literal["pending", "active", "succeeded", "failed", "expired", "cancelled"]
DirectiveDisposition = Literal["accepted", "deferred", "rejected", "completed"]


@dataclass(frozen=True)
class DirectorDirective:
    id: str
    run_id: str
    target_agent_id: str
    objective: str
    mode: DirectiveMode
    priority: str
    issued_tick: int
    expires_at_tick: int
    subject_agent_id: str | None = None
    location_id: str | None = None
    message_hint: str | None = None
    constraints: dict[str, Any] = field(default_factory=dict)
    completion_criteria: dict[str, Any] = field(default_factory=dict)
    source: str = "auto"

    def as_context(self) -> dict[str, Any]:
        return asdict(self)


def compile_directives(
    plan: DirectorPlan,
    *,
    run_id: str,
    issued_tick: int,
    valid_agent_ids: set[str],
    valid_location_ids: set[str],
) -> list[DirectorDirective]:
    targets = [agent_id for agent_id in plan.target_agent_ids if agent_id in valid_agent_ids]
    if not targets or plan.scene_goal == "none":
        return []
    location_id = plan.location_hint if plan.location_hint in valid_location_ids else None
    subject_agent_id = plan.target_agent_id if plan.target_agent_id in valid_agent_ids else None
    mode = _resolve_mode(plan)
    expires_at_tick = issued_tick + max(1, min(plan.cooldown_ticks, 20))
    return [
        DirectorDirective(
            id=str(uuid4()),
            run_id=run_id,
            target_agent_id=agent_id,
            objective=plan.scene_goal,
            mode=mode,
            priority=plan.priority,
            issued_tick=issued_tick,
            expires_at_tick=expires_at_tick,
            subject_agent_id=subject_agent_id,
            location_id=location_id,
            message_hint=plan.message_hint,
            constraints=_build_constraints(
                mode=mode,
                subject_agent_id=subject_agent_id,
                location_id=location_id,
            ),
            completion_criteria=_build_completion_criteria(plan),
            source=plan.source_type,
        )
        for agent_id in targets
    ]


def _resolve_mode(plan: DirectorPlan) -> DirectiveMode:
    enforced_goals = {"shutdown", "weather_change", "power_outage"}
    if plan.scene_goal in enforced_goals:
        return "enforced"
    if plan.urgency in {"immediate", "emergency"} or plan.priority in {"critical", "high"}:
        return "priority"
    return "advisory"


def _build_constraints(
    *, mode: DirectiveMode, subject_agent_id: str | None, location_id: str | None
) -> dict[str, Any]:
    constraints: dict[str, Any] = {"mode": mode}
    if subject_agent_id:
        constraints["target_agent_id"] = subject_agent_id
    if location_id:
        constraints["location_id"] = location_id
    return constraints


def _build_completion_criteria(plan: DirectorPlan) -> dict[str, Any]:
    if plan.location_hint:
        return {"action_type": "move", "target_location_id": plan.location_hint}
    if plan.target_agent_id:
        return {"action_type": "talk", "target_agent_id": plan.target_agent_id}
    return {"accepted_action": True}
