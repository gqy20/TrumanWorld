from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.scenario.runtime.world_design_models import PolicyConfig, RulesConfig, WorldDesignRuntimePackage
from app.sim.action_resolver import ActionIntent
from app.sim.world import AgentState, LocationState, WorldState


def _build_package() -> WorldDesignRuntimePackage:
    return WorldDesignRuntimePackage(
        scenario_id="narrative_world",
        world_config={},
        rules_config=RulesConfig(version=1, rules=[]),
        policy_config=PolicyConfig(
            version=1,
            policy_id="default",
            values={
                "closed_locations": ["cafe"],
                "inspection_level": "high",
                "subject_protection_bias": "high",
            },
        ),
        constitution_text="",
    )


def test_build_rule_facts_maps_actor_target_world_and_policy_fields():
    from app.scenario.runtime.fact_resolver import build_rule_facts, resolve_fact_value

    world = WorldState(
        current_time=datetime(2026, 3, 21, 21, 30, tzinfo=UTC),
        current_tick=42,
        locations={
            "home": LocationState(id="home", name="Home", capacity=2, occupants={"truman"}),
            "cafe": LocationState(
                id="cafe",
                name="Cafe",
                capacity=3,
                occupants={"meryl"},
                location_type="cafe",
            ),
        },
        agents={
            "truman": AgentState(
                id="truman",
                name="Truman",
                location_id="home",
                occupation="insurance clerk",
                workplace_id="office",
                status={"world_role": "truman", "suspicion_score": 0.2},
            ),
            "meryl": AgentState(
                id="meryl",
                name="Meryl",
                location_id="cafe",
                occupation="hospital staff",
                status={"world_role": "cast"},
            ),
        },
    )
    intent = ActionIntent(
        agent_id="truman",
        action_type="move",
        target_location_id="cafe",
        target_agent_id="meryl",
    )

    facts = build_rule_facts(world=world, intent=intent, package=_build_package())

    assert resolve_fact_value(facts, "actor.id") == "truman"
    assert resolve_fact_value(facts, "actor.role") == "truman"
    assert resolve_fact_value(facts, "actor.workplace_id") == "office"
    assert resolve_fact_value(facts, "actor.status.suspicion_score") == 0.2
    assert resolve_fact_value(facts, "target_agent.id") == "meryl"
    assert resolve_fact_value(facts, "target_agent.role") == "cast"
    assert resolve_fact_value(facts, "target_location.id") == "cafe"
    assert resolve_fact_value(facts, "target_location.type") == "cafe"
    assert resolve_fact_value(facts, "target_location.occupancy") == 1
    assert resolve_fact_value(facts, "target_location.capacity_remaining") == 2
    assert resolve_fact_value(facts, "world.current_tick") == 42
    assert resolve_fact_value(facts, "world.time_period") == "night"
    assert resolve_fact_value(facts, "policy.closed_locations") == ["cafe"]
    assert resolve_fact_value(facts, "policy.inspection_level") == "high"


def test_build_rule_facts_uses_nulls_for_missing_targets_and_false_for_missing_location():
    from app.scenario.runtime.fact_resolver import build_rule_facts, resolve_fact_value

    world = WorldState(
        current_time=datetime(2026, 3, 21, 9, 0, tzinfo=UTC),
        locations={
            "home": LocationState(id="home", name="Home", capacity=2, occupants={"truman"}),
        },
        agents={
            "truman": AgentState(
                id="truman",
                name="Truman",
                location_id="home",
                status={},
            ),
        },
    )
    intent = ActionIntent(
        agent_id="truman",
        action_type="talk",
        target_location_id="missing",
        target_agent_id="unknown",
    )

    facts = build_rule_facts(world=world, intent=intent, package=_build_package())

    assert resolve_fact_value(facts, "target_agent.id") is None
    assert resolve_fact_value(facts, "target_agent.location_id") is None
    assert resolve_fact_value(facts, "target_location.exists") is False
    assert resolve_fact_value(facts, "target_location.id") == "missing"
    assert resolve_fact_value(facts, "target_location.capacity_remaining") is None


def test_resolve_fact_value_raises_for_unknown_namespace_or_path():
    from app.scenario.runtime.fact_resolver import build_rule_facts, resolve_fact_value

    world = WorldState(
        current_time=datetime(2026, 3, 21, 9, 0, tzinfo=UTC),
        locations={},
        agents={
            "truman": AgentState(id="truman", name="Truman", location_id="home"),
        },
    )
    intent = ActionIntent(agent_id="truman", action_type="rest")

    facts = build_rule_facts(world=world, intent=intent, package=_build_package())

    with pytest.raises(KeyError):
        resolve_fact_value(facts, "unknown.foo")

    with pytest.raises(KeyError):
        resolve_fact_value(facts, "actor.profile.secret")
