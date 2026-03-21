"""World rules for the bundle-world adapter."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.scenario.bundle_world.types import get_director_guidance
from app.scenario.runtime.world_config import (
    build_world_common_knowledge as build_runtime_world_common_knowledge,
)
from app.scenario.runtime.world_config import load_world_config as load_runtime_world_config
from app.scenario.runtime_config import ScenarioRuntimeConfig, build_scenario_runtime_config
from app.sim.world_queries import (
    build_familiarity_map,
    get_agent,
    get_location,
    list_other_occupants,
)

if TYPE_CHECKING:
    from app.sim.world import WorldState
    from app.store.models import Relationship

RuntimeRoleSemantics = ScenarioRuntimeConfig


def build_runtime_role_semantics(scenario_id: str) -> RuntimeRoleSemantics:
    return build_scenario_runtime_config(scenario_id)


def load_world_config(scenario_id: str | None = None) -> dict[str, Any]:
    return load_runtime_world_config(scenario_id)


def build_perception_context(
    viewer_id: str,
    nearby_agents: list[dict[str, Any]],
    relationships: dict[str, float],
) -> dict[str, Any]:
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

    return {"perceived_others": perceived_agents}


def filter_world_for_role(
    world_role: str,
    world: dict[str, Any],
    semantics: RuntimeRoleSemantics | None = None,
) -> dict[str, Any]:
    resolved = semantics or RuntimeRoleSemantics()
    if world_role == resolved.subject_role:
        return {
            key: value
            for key, value in world.items()
            if not key.startswith("director_") and not key.startswith("cast_")
        }
    return dict(world)


def build_role_context(
    world_role: str,
    world: dict[str, Any],
    semantics: RuntimeRoleSemantics | None = None,
) -> dict[str, Any]:
    resolved = semantics or RuntimeRoleSemantics()
    if world_role == resolved.subject_role:
        context = {
            "perspective": "subjective",
            "focus": "以普通居民的身份体验世界，只根据亲身经历理解周围发生的事",
            "guidance": [
                "不要假设自己知道幕后信息",
                "优先依据眼前线索和熟悉的日常节奏做判断",
            ],
        }
        if resolved.subject_alert_tracking:
            current_alert_score = world.get("self_status", {}).get(resolved.alert_metric, 0.0)
            context["current_alert_score"] = current_alert_score
        return context
    if world_role in resolved.support_role_set():
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


def build_world_common_knowledge(scenario_id: str | None = None) -> dict[str, Any]:
    return build_runtime_world_common_knowledge(scenario_id)


def build_scene_guidance(
    world_role: str,
    world: dict[str, Any],
    semantics: RuntimeRoleSemantics | None = None,
) -> dict[str, Any]:
    resolved = semantics or RuntimeRoleSemantics()
    if world_role not in resolved.support_role_set():
        return {}

    guidance = get_director_guidance(world)
    scene_goal = guidance.get("director_scene_goal")
    if not scene_goal:
        return {}

    base_guidance = {
        "scene_goal": scene_goal,
        "priority": guidance.get("director_priority", "advisory"),
        "message_hint": guidance.get("director_message_hint"),
        "target_agent_id": guidance.get("director_target_agent_id"),
        "location_hint": guidance.get("director_location_hint"),
        "reason": guidance.get("director_reason"),
    }

    manual_goals = {"gather", "activity", "shutdown", "weather_change", "power_outage"}
    if scene_goal in manual_goals:
        base_guidance["is_advisory"] = False
        base_guidance["action_hint"] = _build_action_hint_for_manual_goal(scene_goal, guidance)
    else:
        base_guidance["is_advisory"] = True

    return base_guidance


def _build_action_hint_for_manual_goal(scene_goal: str, guidance: dict[str, Any]) -> str:
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
    return build_perception_context(viewer_agent_id, nearby_agents, relationship_map)
