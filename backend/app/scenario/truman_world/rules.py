"""World rules for TrumanWorld scenario.

Simplified version: Let LLM do the reasoning.
Architecture only passes raw data, LLM infers:
- What someone looks like based on occupation
- What they might be doing based on location
- What they know based on relationship familiarity
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.scenario.truman_world.types import get_director_guidance
from app.sim.world_queries import (
    build_familiarity_map,
    get_agent,
    get_location,
    list_other_occupants,
)

if TYPE_CHECKING:
    from app.sim.world import WorldState
    from app.store.models import Relationship


def build_perception_context(
    viewer_id: str,
    nearby_agents: list[dict[str, Any]],
    relationships: dict[str, float],
) -> dict[str, Any]:
    """Build perception context for agent decision making.

    Simplified: Just pass raw data, let LLM infer:
    - Observable cues from occupation
    - Knowledge level from familiarity
    - Relationship level from familiarity

    Args:
        viewer_id: Viewer agent ID
        nearby_agents: List of nearby agents with basic info
        relationships: Familiarity mapping

    Returns:
        Perception context dict
    """
    perceived_agents = []

    for agent in nearby_agents:
        if agent.get("id") == viewer_id:
            continue

        agent_id = agent.get("id", "")
        familiarity = relationships.get(agent_id, 0.0)

        perceived = {
            "id": agent_id,
            "name": agent.get("name"),
            "occupation": agent.get("occupation"),
            "workplace_id": agent.get("workplace_id"),
            "is_at_workplace": agent.get("is_at_workplace", False),
            "familiarity": familiarity,
        }

        perceived_agents.append(perceived)

    return {
        "perceived_others": perceived_agents,
    }


def filter_world_for_role(world_role: str, world: dict[str, Any]) -> dict[str, Any]:
    """Filter world info based on agent role."""
    if world_role == "truman":
        # Truman shouldn't see director/cast system info
        return {
            key: value
            for key, value in world.items()
            if not key.startswith("director_") and not key.startswith("cast_")
        }
    return dict(world)


def build_role_context(world_role: str, world: dict[str, Any]) -> dict[str, Any]:
    """Build role-specific context for agent."""
    if world_role == "truman":
        return {
            "perspective": "subjective",
            "focus": "以普通居民的身份体验世界，只根据亲身经历理解周围发生的事",
            "current_suspicion_score": world.get("self_status", {}).get("suspicion_score", 0.0),
            "guidance": [
                "不要假设自己知道幕后信息",
                "优先依据眼前线索和熟悉的日常节奏做判断",
            ],
        }
    if world_role == "cast":
        return {
            "perspective": "supporting_cast",
            "focus": "优先保持自然、熟悉、不过分用力的日常互动",
            "guidance": [
                "优先做自然、连续、不会突然破坏日常节奏的动作",
                "场景提示只是软参考，不需要生硬执行",
                "如果信息不足，选择最稳妥、最像熟人日常的回应",
            ],
        }
    return {
        "perspective": "background",
        "focus": "保持低风险、背景化、自然的存在感",
        "guidance": ["优先做简单稳定的动作"],
    }


def build_scene_guidance(world_role: str, world: dict[str, Any]) -> dict[str, Any]:
    """Build scene guidance for cast agents."""
    if world_role != "cast":
        return {}

    guidance = get_director_guidance(world)
    scene_goal = guidance.get("director_scene_goal")
    if not scene_goal:
        return {}

    return {
        "scene_goal": scene_goal,
        "priority": guidance.get("director_priority", "advisory"),
        "message_hint": guidance.get("director_message_hint"),
        "target_agent_id": guidance.get("director_target_agent_id"),
        "location_hint": guidance.get("director_location_hint"),
        "reason": guidance.get("director_reason"),
        "is_advisory": True,
    }


def build_perception_context_for_agent(
    viewer_agent_id: str,
    world: "WorldState",
    relationships: list["Relationship"],
    current_location_id: str | None,
) -> dict[str, Any]:
    """Build perception context for an agent.

    Simplified: Just pass raw agent data, let LLM do all inference.
    """
    if not current_location_id:
        return {}

    location = get_location(world, current_location_id)
    if location is None:
        return {}

    nearby_agent_ids = list_other_occupants(world, viewer_agent_id, current_location_id)
    if not nearby_agent_ids:
        return {"perceived_others": []}

    relationship_map = build_familiarity_map(relationships)

    nearby_agents = []
    for agent_id in nearby_agent_ids:
        agent = get_agent(world, agent_id)
        if agent is None:
            continue

        nearby_agents.append(
            {
                "id": agent.id,
                "name": agent.name,
                "occupation": agent.occupation,
                "workplace_id": agent.workplace_id,
                "is_at_workplace": agent.workplace_id == current_location_id,
            }
        )

    return build_perception_context(
        viewer_id=viewer_agent_id,
        nearby_agents=nearby_agents,
        relationships=relationship_map,
    )
