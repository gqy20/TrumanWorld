from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.scenario.truman_world.rules import (
    build_perception_context_for_agent as build_perception_context_for_agent_rule,
    build_role_context as build_role_context_rule,
    build_scene_guidance as build_scene_guidance_rule,
    filter_world_for_role as filter_world_for_role_rule,
)

if TYPE_CHECKING:
    from app.sim.world import WorldState
    from app.store.models import Relationship


def filter_world_for_role(world_role: str, world: dict[str, Any]) -> dict[str, Any]:
    return filter_world_for_role_rule(world_role, world)


def build_role_context(world_role: str, world: dict[str, Any]) -> dict[str, Any]:
    return build_role_context_rule(world_role, world)


def build_scene_guidance(world_role: str, world: dict[str, Any]) -> dict[str, Any]:
    return build_scene_guidance_rule(world_role, world)


def build_perception_context_for_agent(
    viewer_agent_id: str,
    world: WorldState,
    relationships: list[Relationship],
    current_location_id: str | None,
) -> dict[str, Any]:
    return build_perception_context_for_agent_rule(
        viewer_agent_id=viewer_agent_id,
        world=world,
        relationships=relationships,
        current_location_id=current_location_id,
    )
