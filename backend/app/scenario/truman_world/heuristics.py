"""Heuristics for TrumanWorld scenario.

All agent behavior decisions are delegated to LLM.
This module is kept as a compatibility shim; build_truman_world_decision always returns None.
"""

from __future__ import annotations

from app.cognition.claude.decision_utils import RuntimeDecision
from app.sim.types import RuntimeWorldContext


def build_truman_world_decision(
    *,
    world: RuntimeWorldContext,
    nearby_agent_id: str | None,
    current_location_id: str | None,
    home_location_id: str | None,
    agent_id: str | None = None,
) -> RuntimeDecision | None:
    """No heuristic overrides — all decisions delegated to LLM."""
    return None
