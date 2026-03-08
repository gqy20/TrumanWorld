"""World rules for TrumanWorld scenario.

This module defines the cognitive rules for how agents perceive each other
and infer information from observations. These rules are scenario-specific
and should be injected at the scenario layer.

认知规则设计原则：
1. 可观察性分级：外表 > 行为 > 推断信息
2. 场景上下文：同一行为在不同场所有不同含义
3. 数据驱动：规则配置化，便于扩展
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.sim.world_queries import (
    build_familiarity_map,
    get_agent,
    get_location,
    list_other_occupants,
)

if TYPE_CHECKING:
    from app.sim.world import WorldState
    from app.store.models import Relationship


OCCUPATION_APPEARANCE: dict[str, dict[str, str]] = {
    "insurance clerk": {
        "appearance": "穿着正装",
        "typical_activity": "处理文件",
        "typical_location": "办公室",
    },
    "hospital staff": {
        "appearance": "穿着便装，可能刚下班",
        "typical_activity": "通勤或休息",
        "typical_location": "医院或家中",
    },
    "office coworker": {
        "appearance": "穿着正装",
        "typical_activity": "处理文件",
        "typical_location": "办公室",
    },
    "barista": {
        "appearance": "穿着围裙",
        "typical_activity": "制作咖啡",
        "typical_location": "咖啡馆",
    },
    "shop regular": {
        "appearance": "穿着休闲",
        "typical_activity": "喝咖啡或看书",
        "typical_location": "公共空间",
    },
    "resident": {
        "appearance": "穿着休闲",
        "typical_activity": "日常活动",
        "typical_location": "小镇各处",
    },
}


LOCATION_TYPE_RULES: dict[str, dict[str, str]] = {
    "cafe": {
        "context": "咖啡馆",
        "typical_workers": ["barista"],
        "typical_visitors": ["resident", "shop regular", "office coworker"],
        "activity_hint_customer": "坐在座位上喝咖啡",
        "activity_hint_worker": "在咖啡机后面忙碌",
    },
    "office": {
        "context": "办公室",
        "typical_workers": ["insurance clerk", "office coworker"],
        "typical_visitors": [],
        "activity_hint": "在工位上工作",
    },
    "home": {
        "context": "住宅",
        "typical_workers": [],
        "typical_visitors": [],
        "activity_hint": "在家休息",
    },
    "plaza": {
        "context": "广场",
        "typical_workers": [],
        "typical_visitors": ["resident", "shop regular"],
        "activity_hint": "在广场散步或闲逛",
    },
}


RELATIONSHIP_LEVELS = {
    "family": {
        "min_familiarity": 0.9,
        "knowledge_level": "full",
        "description": "家人，完全了解对方信息",
    },
    "close_friend": {
        "min_familiarity": 0.7,
        "knowledge_level": "high",
        "description": "密友，较了解对方信息",
    },
    "friend": {
        "min_familiarity": 0.5,
        "knowledge_level": "medium",
        "description": "朋友，知道基本情况",
    },
    "acquaintance": {
        "min_familiarity": 0.3,
        "knowledge_level": "low",
        "description": "熟人，点头之交",
    },
    "stranger": {
        "min_familiarity": 0.0,
        "knowledge_level": "none",
        "description": "陌生人，仅能通过观察推断",
    },
}


def build_observable_cues(
    occupation: str | None,
    location_type: str | None,
    is_at_workplace: bool = False,
) -> dict[str, Any]:
    """构建角色的可观察线索。

    Args:
        occupation: 角色职业
        location_type: 当前地点类型
        is_at_workplace: 是否在工作地点

    Returns:
        包含可观察线索的字典
    """
    cues: dict[str, Any] = {}

    if not occupation or occupation not in OCCUPATION_APPEARANCE:
        return cues

    occupation_info = OCCUPATION_APPEARANCE[occupation]
    cues["appearance"] = occupation_info["appearance"]
    cues["typical_activity"] = occupation_info["typical_activity"]

    if location_type and location_type in LOCATION_TYPE_RULES:
        location_info = LOCATION_TYPE_RULES[location_type]

        if is_at_workplace:
            if location_type == "cafe" and occupation in location_info.get("typical_workers", []):
                cues["current_activity_hint"] = location_info.get("activity_hint_worker", "在工作")
            elif location_type == "office":
                cues["current_activity_hint"] = location_info.get("activity_hint", "在工作")
        else:
            if location_type == "cafe":
                cues["current_activity_hint"] = location_info.get(
                    "activity_hint_customer", "喝咖啡"
                )
            elif location_type == "plaza":
                cues["current_activity_hint"] = location_info.get("activity_hint", "闲逛")
            elif location_type == "home":
                cues["current_activity_hint"] = location_info.get("activity_hint", "休息")

    return cues


def infer_knowledge_from_relationship(
    familiarity: float,
    other_occupation: str | None,
    other_workplace: str | None,
) -> dict[str, Any]:
    """根据关系熟悉度推断对对方的了解程度。

    Args:
        familiarity: 熟悉度 (0.0 - 1.0)
        other_occupation: 对方职业
        other_workplace: 对方工作地点

    Returns:
        可推断的知识信息
    """
    knowledge: dict[str, Any] = {"knowledge_level": "none"}

    for level, info in RELATIONSHIP_LEVELS.items():
        if familiarity >= info["min_familiarity"]:
            knowledge["relationship_level"] = level
            knowledge["knowledge_level"] = info["knowledge_level"]
            knowledge["description"] = info["description"]
            break

    knowledge_level = knowledge.get("knowledge_level", "none")

    if knowledge_level in ("full", "high"):
        knowledge["known_occupation"] = other_occupation
        knowledge["known_workplace"] = other_workplace
    elif knowledge_level == "medium":
        knowledge["known_occupation"] = other_occupation
    elif knowledge_level == "low":
        knowledge["is_acquaintance"] = True
    else:
        knowledge["requires_observation"] = True

    return knowledge


def build_perception_context(
    viewer_id: str,
    nearby_agents: list[dict[str, Any]],
    relationships: dict[str, float],
    current_location_type: str | None,
) -> dict[str, Any]:
    """构建感知上下文，注入到 agent 的决策上下文中。

    Args:
        viewer_id: 观察者 ID
        nearby_agents: 附近的 agent 列表，每个包含 id, name, occupation, workplace_id, is_at_workplace
        relationships: 与各 agent 的熟悉度映射
        current_location_type: 当前地点类型

    Returns:
        感知上下文字典
    """
    perceived_agents = []

    for agent in nearby_agents:
        if agent.get("id") == viewer_id:
            continue

        agent_id = agent.get("id", "")
        familiarity = relationships.get(agent_id, 0.0)

        observable = build_observable_cues(
            occupation=agent.get("occupation"),
            location_type=current_location_type,
            is_at_workplace=agent.get("is_at_workplace", False),
        )

        knowledge = infer_knowledge_from_relationship(
            familiarity=familiarity,
            other_occupation=agent.get("occupation"),
            other_workplace=agent.get("workplace_id"),
        )

        perceived = {
            "id": agent_id,
            "name": agent.get("name"),
            "familiarity": familiarity,
            "relationship_level": knowledge.get("relationship_level", "stranger"),
            "observable_cues": observable,
        }

        if knowledge.get("known_occupation"):
            perceived["known_occupation"] = knowledge["known_occupation"]
        if knowledge.get("known_workplace"):
            perceived["known_workplace"] = knowledge["known_workplace"]

        perceived_agents.append(perceived)

    return {
        "perceived_others": perceived_agents,
        "perception_rules": {
            "观察优先": "先看外表和行为，再结合已知信息",
            "推断限制": "不熟悉的陌生人只能通过场景推断职业",
            "记忆整合": "已知的熟人信息来自长期记忆",
        },
    }


def filter_world_for_role(world_role: str, world: dict[str, Any]) -> dict[str, Any]:
    if world_role == "truman":
        return {
            key: value
            for key, value in world.items()
            if not key.startswith("director_") and not key.startswith("cast_")
        }
    return dict(world)


def build_role_context(world_role: str, world: dict[str, Any]) -> dict[str, Any]:
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
    if world_role != "cast":
        return {}

    scene_goal = world.get("director_scene_goal")
    if not scene_goal:
        return {}

    return {
        "scene_goal": scene_goal,
        "priority": world.get("director_priority", "advisory"),
        "message_hint": world.get("director_message_hint"),
        "target_agent_id": world.get("director_target_agent_id"),
        "location_hint": world.get("director_location_hint"),
        "reason": world.get("director_reason"),
        "is_advisory": True,
    }


def build_perception_context_for_agent(
    viewer_agent_id: str,
    world: "WorldState",
    relationships: list["Relationship"],
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

    return build_perception_context(
        viewer_id=viewer_agent_id,
        nearby_agents=nearby_agents,
        relationships=relationship_map,
        current_location_type=location.location_type,
    )
