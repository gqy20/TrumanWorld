"""Compatibility wrappers for the legacy narrative-world rules module."""

from app.scenario.bundle_world.rules import (
    RuntimeRoleSemantics,
    build_perception_context,
    build_perception_context_for_agent,
    build_role_context,
    build_runtime_role_semantics,
    build_scene_guidance,
    build_world_common_knowledge,
    filter_world_for_role,
    load_world_config,
)

__all__ = [
    "RuntimeRoleSemantics",
    "build_perception_context",
    "build_perception_context_for_agent",
    "build_role_context",
    "build_runtime_role_semantics",
    "build_scene_guidance",
    "build_world_common_knowledge",
    "filter_world_for_role",
    "load_world_config",
]
