"""Compatibility wrappers for the legacy narrative-world types module."""

from app.scenario.bundle_world.types import (
    BundleWorldGuidance,
    DirectorGuidance,
    build_agent_profile,
    build_bundle_world_guidance,
    build_director_guidance,
    get_agent_config_id,
    get_bundle_world_guidance,
    get_director_guidance,
    get_world_role,
    merge_bundle_world_agent_profile,
    merge_scenario_agent_profile,
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
