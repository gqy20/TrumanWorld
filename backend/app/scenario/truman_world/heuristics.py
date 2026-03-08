"""Heuristics for TrumanWorld scenario.

Simplified: Let LLM handle suspicion and scene logic.
This module now only provides minimal hooks for scenario-specific overrides.
"""

from __future__ import annotations

from app.agent.providers import RuntimeDecision
from app.protocol.simulation import ACTION_MOVE
from app.sim.types import RuntimeWorldContext


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

    # Handle shift workers (e.g., Meryl at hospital)
    # If agent_id contains "spouse", it's Meryl who works shift schedule
    if agent_id and "spouse" in agent_id.lower():
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
    """Handle shift-based work schedule (fixed schedule based on weekday).

    Fixed schedule:
    - Monday, Wednesday, Friday: morning shift (6:00-14:00)
    - Tuesday, Thursday: evening shift (14:00-22:00)
    - Saturday, Sunday: rest
    """
    hour = world.get("hour", 12)
    weekday = world.get("weekday", 0)  # 0=Monday, 6=Sunday

    # Only make decisions during work hours (6:00 - 22:00)
    if hour < 6 or hour >= 22:
        return None

    # Check if scheduled to work today based on weekday (fixed schedule)
    # weekday: 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun
    if weekday == 5 or weekday == 6:
        # Weekend: rest at home
        if current_location_id and home_location_id and current_location_id != home_location_id:
            return RuntimeDecision(
                action_type=ACTION_MOVE, target_location_id=str(home_location_id)
            )
        return RuntimeDecision(action_type="rest")

    # Weekday work schedule
    # Monday, Wednesday, Friday: morning shift
    # Tuesday, Thursday: evening shift
    if weekday in (0, 2, 4):  # Mon, Wed, Fri
        # Morning shift: work 6:00-14:00
        if hour < 6 or hour >= 14:
            # Before or after shift: rest at home
            if current_location_id and home_location_id and current_location_id != home_location_id:
                return RuntimeDecision(
                    action_type=ACTION_MOVE, target_location_id=str(home_location_id)
                )
            return RuntimeDecision(action_type="rest")
    else:  # Tue, Thu
        # Evening shift: work 14:00-22:00
        if hour < 14:
            # Before shift: rest at home
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
