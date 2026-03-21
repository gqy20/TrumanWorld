"""Bundle-world specific types."""

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
    "BundleWorldGuidance",
    "DirectorGuidance",
    "build_agent_profile",
    "build_bundle_world_guidance",
    "build_director_guidance",
    "get_agent_config_id",
    "get_bundle_world_guidance",
    "get_director_guidance",
    "get_world_role",
    "merge_bundle_world_agent_profile",
    "merge_scenario_agent_profile",
]

BundleWorldGuidance: TypeAlias = ScenarioGuidance
DirectorGuidance: TypeAlias = ScenarioGuidance
build_bundle_world_guidance = build_scenario_guidance
build_director_guidance = build_scenario_guidance
get_bundle_world_guidance = get_scenario_guidance
get_director_guidance = get_scenario_guidance


def merge_bundle_world_agent_profile(
    profile: Mapping[str, Any] | None,
    guidance: BundleWorldGuidance | None = None,
) -> AgentProfile:
    from typing import cast as _cast

    base = _cast("AgentProfile", dict(profile or {}))
    if guidance:
        base.update(guidance)
    return base


def merge_scenario_agent_profile(
    profile: Mapping[str, Any] | None,
    guidance: DirectorGuidance | None = None,
) -> AgentProfile:
    return merge_bundle_world_agent_profile(profile, guidance)
