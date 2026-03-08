from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.sim.world import AgentState, LocationState, WorldState


def get_location(world: "WorldState", location_id: str | None) -> "LocationState | None":
    if not location_id:
        return None
    return world.get_location(location_id)


def get_agent(world: "WorldState", agent_id: str | None) -> "AgentState | None":
    if not agent_id:
        return None
    return world.get_agent(agent_id)


def find_nearby_agent(world: "WorldState", agent_id: str, location_id: str) -> str | None:
    location = get_location(world, location_id)
    if location is None:
        return None

    for occupant_id in sorted(location.occupants):
        if occupant_id != agent_id:
            return occupant_id
    return None


def list_other_occupants(
    world: "WorldState", viewer_agent_id: str, location_id: str | None
) -> list[str]:
    location = get_location(world, location_id)
    if location is None:
        return []
    return [agent_id for agent_id in sorted(location.occupants) if agent_id != viewer_agent_id]


def build_familiarity_map(relationships: Iterable[Any]) -> dict[str, float]:
    return {
        relationship.other_agent_id: float(relationship.familiarity)
        for relationship in relationships
        if getattr(relationship, "other_agent_id", None) is not None
    }
