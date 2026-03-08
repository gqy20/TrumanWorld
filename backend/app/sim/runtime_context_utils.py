from __future__ import annotations

from typing import TYPE_CHECKING

from app.scenario.truman_world.types import DirectorGuidance, get_world_role
from app.sim.types import AgentDecisionSnapshot, RuntimeWorldContext
from app.sim.world_queries import get_agent, get_location

if TYPE_CHECKING:
    from app.sim.world import WorldState


def build_agent_world_context(
    *,
    world: "WorldState",
    current_goal: str | None,
    current_location_id: str | None,
    home_location_id: str | None,
    nearby_agent_id: str | None,
    current_status: dict | None = None,
    truman_suspicion_score: float = 0.0,
    world_role: str | None = None,
    director_guidance: DirectorGuidance | None = None,
    workplace_location_id: str | None = None,
) -> RuntimeWorldContext:
    context = {
        "current_goal": current_goal,
        "current_location_id": current_location_id,
        "home_location_id": home_location_id,
        "workplace_location_id": workplace_location_id,
        "nearby_agent_id": nearby_agent_id,
        "self_status": current_status or {},
        "truman_suspicion_score": truman_suspicion_score,
        **world.time_context(),
    }

    if current_location_id:
        location = get_location(world, current_location_id)
        if location:
            context["current_location_name"] = location.name
            context["current_location_type"] = location.location_type

    if nearby_agent_id:
        nearby_agent = get_agent(world, nearby_agent_id)
        if nearby_agent:
            context["nearby_agent"] = {
                "id": nearby_agent.id,
                "name": nearby_agent.name,
                "occupation": nearby_agent.occupation,
            }

    if world_role:
        context["world_role"] = world_role
    if director_guidance:
        context.update(_normalize_director_guidance(director_guidance))

    return context


def extract_truman_suspicion_from_agent_data(
    agent_data: list[AgentDecisionSnapshot],
    world: "WorldState",
) -> float:
    for agent_snapshot in agent_data:
        profile = agent_snapshot.profile or {}
        if get_world_role(profile) != "truman":
            continue
        state = get_agent(world, agent_snapshot.id)
        if state is None:
            continue
        return float((state.status or {}).get("suspicion_score", 0.0) or 0.0)
    return 0.0


def _normalize_director_guidance(guidance: DirectorGuidance) -> DirectorGuidance:
    scene_goal = guidance.get("director_scene_goal")
    if scene_goal is None:
        return {}

    normalized: DirectorGuidance = {"director_scene_goal": scene_goal}
    normalized["director_priority"] = guidance.get("director_priority") or "advisory"

    for key in (
        "director_message_hint",
        "director_target_agent_id",
        "director_location_hint",
        "director_reason",
    ):
        value = guidance.get(key)
        if value is not None:
            normalized[key] = value

    return normalized
