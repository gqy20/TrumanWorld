"""TrumanWorld-specific types.

Generic types (AgentProfile, ScenarioGuidance, get_world_role, get_agent_config_id,
build_agent_profile, merge_agent_profile) now live in app.scenario.types.
This module keeps TrumanWorld-private extensions and re-exports the generics
under their old names for backward compatibility within this package.
"""

from __future__ import annotations

from typing import Any, Literal, Mapping, TypedDict

# ---------------------------------------------------------------------------
# Re-export generic types under legacy names used inside truman_world/
# ---------------------------------------------------------------------------
from app.scenario.types import (
    AgentProfile as ScenarioAgentProfile,
    WorldRole,
    get_world_role,
    get_agent_config_id,
    build_agent_profile as build_scenario_agent_profile,
)

__all__ = [
    "DirectorGuidance",
    "ScenarioAgentProfile",
    "WorldRole",
    "get_world_role",
    "get_agent_config_id",
    "build_scenario_agent_profile",
    "merge_scenario_agent_profile",
    "build_director_guidance",
    "get_director_guidance",
]


# ---------------------------------------------------------------------------
# TrumanWorld-private: Director guidance
# ---------------------------------------------------------------------------


class DirectorGuidance(TypedDict, total=False):
    director_scene_goal: str
    director_priority: str
    director_message_hint: str
    director_target_agent_id: str
    director_location_hint: str
    director_reason: str


def build_director_guidance(
    *,
    scene_goal: str | None,
    priority: str | None,
    message_hint: str | None,
    target_agent_id: str | None,
    location_hint: str | None,
    reason: str | None,
) -> DirectorGuidance:
    guidance: DirectorGuidance = {}
    if scene_goal is None:
        return guidance

    guidance["director_scene_goal"] = scene_goal
    if priority is not None:
        guidance["director_priority"] = priority
    if message_hint is not None:
        guidance["director_message_hint"] = message_hint
    if target_agent_id is not None:
        guidance["director_target_agent_id"] = target_agent_id
    if location_hint is not None:
        guidance["director_location_hint"] = location_hint
    if reason is not None:
        guidance["director_reason"] = reason
    return guidance


def get_director_guidance(profile: Mapping[str, Any] | None) -> DirectorGuidance:
    if not profile:
        return {}
    return build_director_guidance(
        scene_goal=_as_optional_str(profile.get("director_scene_goal")),
        priority=_as_optional_str(profile.get("director_priority")),
        message_hint=_as_optional_str(profile.get("director_message_hint")),
        target_agent_id=_as_optional_str(profile.get("director_target_agent_id")),
        location_hint=_as_optional_str(profile.get("director_location_hint")),
        reason=_as_optional_str(profile.get("director_reason")),
    )


def merge_scenario_agent_profile(
    profile: Mapping[str, Any] | None,
    guidance: DirectorGuidance | None = None,
) -> "ScenarioAgentProfile":
    """Merge a profile dict with optional TrumanWorld DirectorGuidance."""
    from typing import cast as _cast
    from app.scenario.types import AgentProfile
    base = _cast(AgentProfile, dict(profile or {}))
    if guidance:
        base.update(guidance)
    return base


def _as_optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None
