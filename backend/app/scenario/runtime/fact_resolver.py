"""Resolve runtime state into platform fact namespaces."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.scenario.runtime.world_design_models import WorldDesignRuntimePackage
from app.sim.relationship_policy import derive_relationship_level
from app.sim.world import AgentState, LocationState, WorldState

if TYPE_CHECKING:
    from app.sim.action_resolver import ActionIntent


def build_rule_facts(
    *,
    world: WorldState,
    intent: ActionIntent,
    package: WorldDesignRuntimePackage,
) -> dict[str, Any]:
    actor = world.get_agent(intent.agent_id)
    target_agent = world.get_agent(intent.target_agent_id) if intent.target_agent_id else None
    target_location = (
        world.get_location(intent.target_location_id) if intent.target_location_id else None
    )

    return {
        "actor": _build_agent_facts(actor),
        "target_agent": _build_agent_facts(
            target_agent,
            relationship_context=_build_relationship_facts(world, intent.agent_id, intent.target_agent_id),
        ),
        "target_location": _build_location_facts(target_location, intent.target_location_id),
        "world": _build_world_facts(world),
        "policy": _build_policy_facts(world, package),
    }


def resolve_fact_value(facts: dict[str, Any], fact_path: str) -> Any:
    current: Any = facts
    for segment in fact_path.split("."):
        if not isinstance(current, dict) or segment not in current:
            msg = f"Unknown fact path: {fact_path}"
            raise KeyError(msg)
        current = current[segment]
    return current


def _build_agent_facts(
    agent: AgentState | None,
    *,
    relationship_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if agent is None:
        return {
            "id": None,
            "name": None,
            "role": None,
            "occupation": None,
            "location_id": None,
            "home_location_id": None,
            "workplace_id": None,
            "status": {},
            "relationship_level": None,
            "familiarity": None,
            "trust": None,
            "affinity": None,
            "relation_type": None,
        }

    relationship = relationship_context or {}
    return {
        "id": agent.id,
        "name": agent.name,
        "role": agent.status.get("world_role"),
        "occupation": agent.occupation,
        "location_id": agent.location_id,
        "home_location_id": None,
        "workplace_id": agent.workplace_id,
        "status": dict(agent.status),
        "relationship_level": relationship.get("relationship_level"),
        "familiarity": relationship.get("familiarity"),
        "trust": relationship.get("trust"),
        "affinity": relationship.get("affinity"),
        "relation_type": relationship.get("relation_type"),
    }


def _build_location_facts(
    location: LocationState | None,
    requested_location_id: str | None,
) -> dict[str, Any]:
    if location is None:
        return {
            "id": requested_location_id,
            "name": None,
            "exists": False,
            "type": None,
            "capacity": None,
            "occupancy": None,
            "capacity_remaining": None,
            "attributes": {},
        }

    occupancy = len(location.occupants)
    return {
        "id": location.id,
        "name": location.name,
        "exists": True,
        "type": location.location_type,
        "capacity": location.capacity,
        "occupancy": occupancy,
        "capacity_remaining": location.capacity - occupancy,
        "attributes": {},
    }


def _build_world_facts(world: WorldState) -> dict[str, Any]:
    time_context = world.time_context()
    return {
        "current_tick": world.current_tick,
        "current_time": time_context["current_time"],
        "time_period": time_context["time_period"],
        "weekday": time_context["weekday"],
        "weekday_name": time_context["weekday_name"],
        "is_weekend": time_context["is_weekend"],
    }


def _build_relationship_facts(
    world: WorldState,
    actor_agent_id: str,
    target_agent_id: str | None,
) -> dict[str, Any] | None:
    if not target_agent_id:
        return None

    relationship_contexts = getattr(world, "relationship_contexts", None)
    if not isinstance(relationship_contexts, dict):
        return None
    actor_relationships = relationship_contexts.get(actor_agent_id)
    if not isinstance(actor_relationships, dict):
        return None
    relationship = actor_relationships.get(target_agent_id)
    if not isinstance(relationship, dict):
        return None

    familiarity = float(relationship.get("familiarity", 0.0) or 0.0)
    trust = float(relationship.get("trust", 0.0) or 0.0)
    affinity = float(relationship.get("affinity", 0.0) or 0.0)
    relation_type = relationship.get("relation_type")
    relationship_level = relationship.get("relationship_level") or derive_relationship_level(
        familiarity=familiarity,
        trust=trust,
        affinity=affinity,
        relation_type=relation_type,
    )
    return {
        "familiarity": familiarity,
        "trust": trust,
        "affinity": affinity,
        "relation_type": relation_type,
        "relationship_level": relationship_level,
    }


def _build_policy_facts(
    world: WorldState,
    package: WorldDesignRuntimePackage,
) -> dict[str, Any]:
    policy = dict(package.policy_config.values or {})
    world_effects = getattr(world, "world_effects", {}) or {}

    closed_locations = _merge_unique_str_lists(
        policy.get("closed_locations"),
        _active_effect_location_ids(
            world,
            world_effects.get("location_shutdowns"),
        ),
    )
    if closed_locations:
        policy["closed_locations"] = closed_locations

    power_outage_locations = _merge_unique_str_lists(
        policy.get("power_outage_locations"),
        _active_effect_location_ids(
            world,
            world_effects.get("power_outages"),
        ),
    )
    policy["power_outage_locations"] = power_outage_locations

    return policy


def _active_effect_location_ids(world: WorldState, effects: Any) -> list[str]:
    if not isinstance(effects, list):
        return []

    active_location_ids: list[str] = []
    current_tick = getattr(world, "current_tick", 0)
    for effect in effects:
        if not isinstance(effect, dict):
            continue
        location_id = effect.get("location_id")
        if not isinstance(location_id, str) or not location_id:
            continue
        start_tick = effect.get("start_tick")
        end_tick = effect.get("end_tick")
        if isinstance(start_tick, int) and current_tick < start_tick:
            continue
        if isinstance(end_tick, int) and current_tick >= end_tick:
            continue
        active_location_ids.append(location_id)
    return active_location_ids


def _merge_unique_str_lists(*values: Any) -> list[str]:
    merged: list[str] = []
    for value in values:
        if not isinstance(value, list):
            continue
        for item in value:
            if isinstance(item, str) and item not in merged:
                merged.append(item)
    return merged
