"""Heuristics for bundle-world fallback decisions."""

from __future__ import annotations

from app.cognition.claude.decision_utils import RuntimeDecision
from app.scenario.runtime_config import RuntimeRoleSemantics
from app.sim.types import RuntimeWorldContext


def _get_guidance_value(world: RuntimeWorldContext, key: str) -> str | None:
    raw = world.get(key) or world.get(f"director_{key}")
    return raw if isinstance(raw, str) and raw else None


def _build_fallback_message(
    *,
    world_role: str | None,
    scene_goal: str | None,
    message_hint: str | None,
    semantics: RuntimeRoleSemantics | None = None,
) -> str:
    resolved = semantics or RuntimeRoleSemantics()
    if message_hint:
        return message_hint
    if scene_goal == "gather":
        return "我们去广场那边看看吧。"
    if world_role in set(resolved.support_roles):
        return "嗨，刚好碰到你，聊两句吧。"
    return "嗨，今天怎么样？"


def build_bundle_world_decision(
    *,
    world: RuntimeWorldContext,
    nearby_agent_id: str | None,
    current_location_id: str | None,
    home_location_id: str | None,
    agent_id: str | None = None,
    semantics: RuntimeRoleSemantics | None = None,
) -> RuntimeDecision | None:
    world_role = world.get("world_role") if isinstance(world.get("world_role"), str) else None
    scene_goal = _get_guidance_value(world, "scene_goal")
    message_hint = _get_guidance_value(world, "message_hint")
    target_agent_id = _get_guidance_value(world, "target_agent_id")
    location_hint = _get_guidance_value(world, "location_hint")

    if nearby_agent_id and (target_agent_id is None or target_agent_id == nearby_agent_id):
        return RuntimeDecision(
            action_type="talk",
            target_agent_id=nearby_agent_id,
            message=_build_fallback_message(
                world_role=world_role,
                scene_goal=scene_goal,
                message_hint=message_hint,
                semantics=semantics,
            ),
        )

    if location_hint and location_hint != current_location_id:
        return RuntimeDecision(
            action_type="move",
            target_location_id=location_hint,
        )

    if home_location_id and home_location_id != current_location_id:
        return RuntimeDecision(
            action_type="move",
            target_location_id=home_location_id,
        )

    return RuntimeDecision(action_type="rest")


def build_narrative_world_decision(**kwargs):
    return build_bundle_world_decision(**kwargs)
