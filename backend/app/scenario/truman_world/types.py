"""TrumanWorld-specific types.

Generic types (AgentProfile, ScenarioGuidance, get_world_role, get_agent_config_id,
build_agent_profile, merge_agent_profile) now live in app.scenario.types.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeAlias

from app.scenario.types import (
    AgentProfile,
    ScenarioGuidance,
    build_agent_profile,
    build_scenario_guidance,
    get_agent_config_id,
    get_scenario_guidance,
    get_world_role,
)

__all__ = [
    "DirectorGuidance",
    "build_agent_profile",
    "build_director_guidance",
    "get_agent_config_id",
    "get_director_guidance",
    "get_world_role",
    "merge_scenario_agent_profile",
]


# ---------------------------------------------------------------------------
# TrumanWorld-private: Director guidance
# ---------------------------------------------------------------------------


DirectorGuidance: TypeAlias = ScenarioGuidance
build_director_guidance = build_scenario_guidance
get_director_guidance = get_scenario_guidance


def merge_scenario_agent_profile(
    profile: Mapping[str, Any] | None,
    guidance: DirectorGuidance | None = None,
) -> AgentProfile:
    """Merge a profile dict with optional TrumanWorld DirectorGuidance."""
    from typing import cast as _cast

    base = _cast("AgentProfile", dict(profile or {}))
    if guidance:
        base.update(guidance)
    return base
