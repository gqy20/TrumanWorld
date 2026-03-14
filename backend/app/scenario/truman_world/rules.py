"""World rules for TrumanWorld scenario.

Simplified version: Let LLM do the reasoning.
Architecture only passes raw data, LLM infers:
- What someone looks like based on occupation
- What they might be doing based on location
- What they know based on relationship familiarity
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

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


# 加载世界配置
_WORLD_CONFIG_PATH = Path(__file__).parent / "world_config.yml"
_WORLD_CONFIG_CACHE: dict[str, Any] | None = None


def load_world_config() -> dict[str, Any]:
    """Load world configuration from YAML file.

    Uses caching to avoid repeated file reads.
    This is the public API for accessing world configuration.
    """
    global _WORLD_CONFIG_CACHE
    if _WORLD_CONFIG_CACHE is None:
        with open(_WORLD_CONFIG_PATH, encoding="utf-8") as f:
            _WORLD_CONFIG_CACHE = yaml.safe_load(f)
    return _WORLD_CONFIG_CACHE


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


def build_world_common_knowledge() -> dict[str, Any]:
    """Build world common knowledge shared by all agents in TrumanWorld.

    This defines the shared understanding of how the world works,
    including daily rhythms, location purposes, and social norms.

    Configuration is loaded from world_config.yml for easy management.
    """
    config = load_world_config()
    return {
        "daily_rhythm": config.get("daily_rhythm", {}),
        "location_purposes": config.get("location_purposes", {}),
        "social_norms": config.get("social_norms", []),
        "location_descriptions": config.get("location_descriptions", {}),
        "time_suggestions": config.get("time_suggestions", {}),
    }


def build_scene_guidance(world_role: str, world: dict[str, Any]) -> dict[str, Any]:
    """Build scene guidance for cast agents.

    Supports both automatic intervention goals (soft_check_in, keep_scene_natural, etc.)
    and manual injection goals (gather, activity, shutdown, weather_change, power_outage).
    """
    if world_role != "cast":
        return {}

    guidance = get_director_guidance(world)
    scene_goal = guidance.get("director_scene_goal")
    if not scene_goal:
        return {}

    # Base guidance structure
    base_guidance = {
        "scene_goal": scene_goal,
        "priority": guidance.get("director_priority", "advisory"),
        "message_hint": guidance.get("director_message_hint"),
        "target_agent_id": guidance.get("director_target_agent_id"),
        "location_hint": guidance.get("director_location_hint"),
        "reason": guidance.get("director_reason"),
    }

    # Manual injection goals are typically more directive
    manual_goals = {"gather", "activity", "shutdown", "weather_change", "power_outage"}
    if scene_goal in manual_goals:
        base_guidance["is_advisory"] = False
        base_guidance["action_hint"] = _build_action_hint_for_manual_goal(scene_goal, guidance)
    else:
        base_guidance["is_advisory"] = True

    return base_guidance


def _build_action_hint_for_manual_goal(scene_goal: str, guidance: dict[str, Any]) -> str:
    """Build action hint for manual injection goals.

    This helps Cast Agents understand what actions to take for manual events.
    """
    message_hint = guidance.get("director_message_hint", "")
    location_hint = guidance.get("director_location_hint")

    if scene_goal == "gather":
        if location_hint:
            return (
                f"收到广播消息: '{message_hint}'。"
                f"如果方便，考虑前往指定地点参与。"
                f"到达后可以与周围的人自然互动。"
            )
        return f"收到广播消息: '{message_hint}'。留意周围情况，保持自然日常状态。"

    if scene_goal == "activity":
        if location_hint:
            return (
                f"有活动举办: '{message_hint}'。"
                f"如果在附近或感兴趣，可以前往参与。"
                f"保持轻松自然的参与态度。"
            )
        return f"有活动举办: '{message_hint}'。可以根据自己的情况决定是否参与。"

    if scene_goal == "shutdown":
        if location_hint:
            return f"地点关闭通知: '{message_hint}'。请避开该地点，选择其他合适的去处。"
        return f"地点关闭通知: '{message_hint}'。请注意调整行程安排。"

    if scene_goal == "weather_change":
        return f"天气变化: '{message_hint}'。请注意天气影响，调整户外活动计划。"

    if scene_goal == "power_outage":
        if location_hint:
            return (
                f"停电通知: '{message_hint}'。"
                f"你所在世界的 {location_hint} 可能受到影响。"
                "请自然表现出对停电的反应，并调整当前安排。"
            )
        return f"停电通知: '{message_hint}'。请自然表现出对停电的反应。"

    return "请根据情况做出合适的反应。"


def build_perception_context_for_agent(
    viewer_agent_id: str,
    world: WorldState,
    relationships: list[Relationship],
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
