"""Heuristics for TrumanWorld scenario.

Simplified: Let LLM handle suspicion and scene logic.
This module now only provides minimal hooks for scenario-specific overrides.
"""

from __future__ import annotations

from app.agent.providers import RuntimeDecision
from app.protocol.simulation import ACTION_MOVE
from app.scenario.truman_world.rules import load_world_config
from app.sim.types import RuntimeWorldContext


# 加载轮班工作配置
_SHIFT_WORK_CONFIG = load_world_config().get("shift_work_config", {})
_SHIFT_TYPES = _SHIFT_WORK_CONFIG.get("shift_types", {})
_DEFAULT_SCHEDULE = _SHIFT_WORK_CONFIG.get("default_schedule", {})


def build_truman_world_decision(
    *,
    world: RuntimeWorldContext,
    nearby_agent_id: str | None,
    current_location_id: str | None,
    home_location_id: str | None,
    agent_id: str | None = None,
) -> RuntimeDecision | None:
    """Build scenario-specific decision override.

    Simplified: Only handle extreme cases (very high suspicion requiring immediate action).
    All other decisions are left to LLM.
    """
    world_role = world.get("world_role")
    self_status = world.get("self_status", {}) or {}
    suspicion_score = float(self_status.get("suspicion_score", 0.0) or 0.0)

    # Only handle extreme suspicion: go home immediately
    if world_role == "truman":
        if suspicion_score >= 0.95 and home_location_id and current_location_id != home_location_id:
            return RuntimeDecision(
                action_type=ACTION_MOVE, target_location_id=str(home_location_id)
            )

    # Handle shift workers: read schedule_type from world context (injected from agent profile)
    # This replaces the brittle "spouse" in agent_id string match.
    schedule_type = world.get("schedule_type")
    if schedule_type == "shift":
        shift_decision = _handle_shift_work(
            world=world,
            current_location_id=current_location_id,
            home_location_id=home_location_id,
        )
        if shift_decision is not None:
            return shift_decision

    # All other cases: let LLM decide
    return None


def _handle_shift_work(
    world: RuntimeWorldContext,
    current_location_id: str | None,
    home_location_id: str | None,
) -> RuntimeDecision | None:
    """Handle shift-based work schedule (configured in world_config.yml).
    
    Schedule is loaded from YAML configuration.
    """
    hour = world.get("hour", 12)
    weekday = world.get("weekday", 0)  # 0=Monday, 6=Sunday
    
    # Get today's shift from config
    today_shift = _DEFAULT_SCHEDULE.get(str(weekday))
    
    # Weekend or rest day
    if today_shift is None:
        if current_location_id and home_location_id and current_location_id != home_location_id:
            return RuntimeDecision(
                action_type=ACTION_MOVE, target_location_id=str(home_location_id)
            )
        return RuntimeDecision(action_type="rest")
    
    # Get shift hours from config
    shift_config = _SHIFT_TYPES.get(today_shift, {})
    start_hour = shift_config.get("start_hour", 6)
    end_hour = shift_config.get("end_hour", 14)
    
    # Only make decisions during work hours range (6:00 - 22:00)
    if hour < 6 or hour >= 22:
        return None
    
    # Before shift: rest at home
    if hour < start_hour:
        if current_location_id and home_location_id and current_location_id != home_location_id:
            return RuntimeDecision(
                action_type=ACTION_MOVE, target_location_id=str(home_location_id)
            )
        return RuntimeDecision(action_type="rest")
    
    # After shift: rest at home
    if hour >= end_hour:
        if current_location_id and home_location_id and current_location_id != home_location_id:
            return RuntimeDecision(
                action_type=ACTION_MOVE, target_location_id=str(home_location_id)
            )
        return RuntimeDecision(action_type="rest")
    
    # During shift hours: go to workplace if not already there
    workplace_location_id = world.get("workplace_location_id")
    if workplace_location_id and current_location_id != workplace_location_id:
        return RuntimeDecision(
            action_type=ACTION_MOVE, target_location_id=str(workplace_location_id)
        )
    
    return None
