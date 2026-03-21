from __future__ import annotations

from typing import Any

from app.sim.action_resolver import ActionResult
from app.sim.world import WorldState


def apply_governance_consequences(
    world: WorldState,
    result: ActionResult,
    *,
    policy_values: dict[str, Any] | None = None,
) -> None:
    governance_execution = result.governance_execution
    if governance_execution is None:
        return
    if governance_execution.decision not in {"record_only", "warn", "block"}:
        return

    agent_id = result.event_payload.get("agent_id")
    if not isinstance(agent_id, str) or not agent_id:
        return

    agent = world.get_agent(agent_id)
    if agent is None:
        return

    status = dict(agent.status or {})
    if governance_execution.decision in {"warn", "block"}:
        status["warning_count"] = int(status.get("warning_count", 0) or 0) + 1
    if governance_execution.decision == "record_only":
        status["observation_count"] = int(status.get("observation_count", 0) or 0) + 1

    current_attention = float(status.get("governance_attention_score", 0.0) or 0.0)
    resolved_policy = policy_values or {}
    delta = (
        float(resolved_policy.get("record_attention_delta", 0.02) or 0.02)
        if governance_execution.decision == "record_only"
        else (
            float(resolved_policy.get("warn_attention_delta", 0.05) or 0.05)
            if governance_execution.decision == "warn"
            else float(resolved_policy.get("block_attention_delta", 0.15) or 0.15)
        )
    )
    cap = float(resolved_policy.get("attention_score_cap", 1.0) or 1.0)
    status["governance_attention_score"] = round(min(cap, current_attention + delta), 6)
    agent.status = status


def apply_governance_attention_decay(
    world: WorldState,
    *,
    days_elapsed: int,
    policy_values: dict[str, Any] | None = None,
) -> None:
    if days_elapsed <= 0:
        return

    resolved_policy = policy_values or {}
    decay_per_day = float(resolved_policy.get("attention_decay_per_day", 0.05) or 0.05)
    if decay_per_day <= 0:
        return

    total_decay = decay_per_day * days_elapsed
    for agent in world.agents.values():
        status = dict(agent.status or {})
        current_attention = float(status.get("governance_attention_score", 0.0) or 0.0)
        if current_attention <= 0:
            continue
        status["governance_attention_score"] = round(
            max(0.0, current_attention - total_decay),
            6,
        )
        agent.status = status
