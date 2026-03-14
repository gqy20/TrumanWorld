from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.sim.world import AgentState, LocationState, WorldState


def get_location(world: WorldState, location_id: str | None) -> LocationState | None:
    if not location_id:
        return None
    return world.get_location(location_id)


def get_agent(world: WorldState, agent_id: str | None) -> AgentState | None:
    if not agent_id:
        return None
    return world.get_agent(agent_id)


def find_nearby_agent(world: WorldState, agent_id: str, location_id: str) -> str | None:
    location = get_location(world, location_id)
    if location is None:
        return None

    for occupant_id in sorted(location.occupants):
        if occupant_id != agent_id:
            return occupant_id
    return None


def list_other_occupants(
    world: WorldState, viewer_agent_id: str, location_id: str | None
) -> list[str]:
    location = get_location(world, location_id)
    if location is None:
        return []
    return [agent_id for agent_id in sorted(location.occupants) if agent_id != viewer_agent_id]


def get_location_occupants(
    world: WorldState, location_id: str | None, exclude_agent_id: str | None = None
) -> list[dict[str, Any]]:
    """Get all agents at a location with their basic info.

    Args:
        world: World state
        location_id: Location ID
        exclude_agent_id: Optional agent ID to exclude from results

    Returns:
        List of agent info dicts with id, name, occupation, workplace_id, is_at_workplace
    """
    location = get_location(world, location_id)
    if location is None:
        return []

    occupants = []
    for agent_id in location.occupants:
        if agent_id == exclude_agent_id:
            continue
        agent = get_agent(world, agent_id)
        if agent is None:
            continue
        occupants.append(
            {
                "id": agent.id,
                "name": agent.name,
                "occupation": agent.occupation,
                "workplace_id": agent.workplace_id,
                "is_at_workplace": agent.workplace_id == location_id,
            }
        )
    return occupants


def build_familiarity_map(relationships: Iterable[Any]) -> dict[str, float]:
    return {
        relationship.other_agent_id: float(relationship.familiarity)
        for relationship in relationships
        if getattr(relationship, "other_agent_id", None) is not None
    }
