"""Resolve runtime state into platform fact namespaces."""

from __future__ import annotations

from typing import Any

from app.scenario.runtime.world_design_models import WorldDesignRuntimePackage
from app.sim.action_resolver import ActionIntent
from app.sim.world import AgentState, LocationState, WorldState


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
        "target_agent": _build_agent_facts(target_agent),
        "target_location": _build_location_facts(target_location, intent.target_location_id),
        "world": _build_world_facts(world),
        "policy": dict(package.policy_config.values),
    }


def resolve_fact_value(facts: dict[str, Any], fact_path: str) -> Any:
    current: Any = facts
    for segment in fact_path.split("."):
        if not isinstance(current, dict) or segment not in current:
            msg = f"Unknown fact path: {fact_path}"
            raise KeyError(msg)
        current = current[segment]
    return current


def _build_agent_facts(agent: AgentState | None) -> dict[str, Any]:
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
        }

    return {
        "id": agent.id,
        "name": agent.name,
        "role": agent.status.get("world_role"),
        "occupation": agent.occupation,
        "location_id": agent.location_id,
        "home_location_id": None,
        "workplace_id": agent.workplace_id,
        "status": dict(agent.status),
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
