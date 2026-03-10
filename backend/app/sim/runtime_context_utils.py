from __future__ import annotations

from typing import TYPE_CHECKING

from app.scenario.types import get_world_role
from app.scenario.truman_world.types import DirectorGuidance
from app.sim.types import AgentDecisionSnapshot, RuntimeWorldContext
from app.sim.world_queries import get_agent, get_location, get_location_occupants

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
    current_plan: dict | None = None,
) -> RuntimeWorldContext:
    # Identify social locations (plaza / cafe) for talk-goal navigation
    social_location_ids = [
        loc_id
        for loc_id, loc in world.locations.items()
        if loc.location_type in {"plaza", "cafe"}
    ]

    context = {
        "current_goal": current_goal,
        "current_location_id": current_location_id,
        "home_location_id": home_location_id,
        "workplace_location_id": workplace_location_id,
        "known_location_ids": sorted(world.locations.keys()),
        "social_location_ids": social_location_ids,
        "nearby_agent_id": nearby_agent_id,
        "self_status": current_status or {},
        "truman_suspicion_score": truman_suspicion_score,
        **world.time_context(),
    }

    # Inject daily schedule so LLM can self-determine appropriate behavior per time period
    if current_plan:
        context["daily_schedule"] = current_plan

    if current_location_id:
        location = get_location(world, current_location_id)
        if location:
            context["current_location_name"] = location.name
            context["current_location_type"] = location.location_type

    # Add all occupants at current location (for multi-agent awareness)
    if current_location_id:
        context["location_occupants"] = get_location_occupants(
            world, current_location_id, exclude_agent_id=None
        )

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


def inject_profile_fields_into_context(
    context: dict,
    profile: dict | None,
) -> None:
    """Inject selected agent profile fields into the world context dict.

    Currently injects: schedule_type (for heuristics shift detection).
    Called by service after build_agent_world_context.
    """
    if not profile:
        return
    schedule_type = profile.get("schedule_type")
    if schedule_type:
        context["schedule_type"] = schedule_type


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
