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
            return RuntimeDecision(action_type=ACTION_MOVE, target_location_id=str(home_location_id))

    # All other cases: let LLM decide
    return None
