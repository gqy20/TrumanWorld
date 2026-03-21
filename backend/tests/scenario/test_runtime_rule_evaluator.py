from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.scenario.runtime.world_design_models import (
    PolicyConfig,
    RuleConditionConfig,
    RuleConfigItem,
    RuleOutcomeConfig,
    RuleTriggerConfig,
    RulesConfig,
    WorldDesignRuntimePackage,
)
from app.sim.action_resolver import ActionIntent
from app.sim.world import AgentState, LocationState, WorldState


def _build_world() -> WorldState:
    return WorldState(
        current_time=datetime(2026, 3, 21, 21, 30, tzinfo=UTC),
        current_tick=42,
        locations={
            "home": LocationState(id="home", name="Home", capacity=2, occupants={"truman"}),
            "cafe": LocationState(
                id="cafe",
                name="Cafe",
                capacity=1,
                occupants={"meryl"},
                location_type="cafe",
            ),
        },
        agents={
            "truman": AgentState(
                id="truman",
                name="Truman",
                location_id="home",
                workplace_id="office",
                status={"world_role": "truman", "suspicion_score": 0.2},
            ),
            "meryl": AgentState(
                id="meryl",
                name="Meryl",
                location_id="cafe",
                status={"world_role": "cast"},
            ),
        },
    )


def _build_package(rules: list[RuleConfigItem]) -> WorldDesignRuntimePackage:
    return WorldDesignRuntimePackage(
        scenario_id="narrative_world",
        world_config={},
        rules_config=RulesConfig(version=1, rules=rules),
        policy_config=PolicyConfig(
            version=1,
            policy_id="default",
            values={
                "closed_locations": ["cafe"],
                "inspection_level": "high",
            },
        ),
        constitution_text="",
    )


def test_rule_evaluator_returns_highest_priority_matching_rule():
    from app.scenario.runtime.rule_evaluator import evaluate_rules

    rules = [
        RuleConfigItem(
            rule_id="night_talk_risk",
            name="Night Talk Risk",
            trigger=RuleTriggerConfig(action_types=["talk"]),
            conditions=[
                RuleConditionConfig(fact="world.time_period", op="eq", value="night"),
            ],
            outcome=RuleOutcomeConfig(decision="soft_risk", reason="night_risk"),
            priority=100,
        ),
        RuleConfigItem(
            rule_id="closed_location",
            name="Closed Location",
            trigger=RuleTriggerConfig(action_types=["move"]),
            conditions=[
                RuleConditionConfig(
                    fact="target_location.id", op="in", value_from="policy.closed_locations"
                ),
            ],
            outcome=RuleOutcomeConfig(decision="violates_rule", reason="location_closed"),
            priority=800,
        ),
        RuleConfigItem(
            rule_id="full_location",
            name="Full Location",
            trigger=RuleTriggerConfig(action_types=["move"]),
            conditions=[
                RuleConditionConfig(fact="target_location.capacity_remaining", op="lte", value=0),
            ],
            outcome=RuleOutcomeConfig(decision="impossible", reason="location_full"),
            priority=900,
        ),
    ]

    result = evaluate_rules(
        world=_build_world(),
        intent=ActionIntent(agent_id="truman", action_type="move", target_location_id="cafe"),
        package=_build_package(rules),
    )

    assert result.decision == "impossible"
    assert result.primary_rule_id == "full_location"
    assert result.reason == "location_full"
    assert set(result.matched_rule_ids) == {"closed_location", "full_location"}


def test_rule_evaluator_supports_value_from_fact_comparisons():
    from app.scenario.runtime.rule_evaluator import evaluate_rules

    rules = [
        RuleConfigItem(
            rule_id="working_outside_workplace",
            name="Working Outside Workplace",
            trigger=RuleTriggerConfig(action_types=["work"]),
            conditions=[
                RuleConditionConfig(
                    fact="actor.workplace_id",
                    op="neq",
                    value_from="actor.location_id",
                ),
            ],
            outcome=RuleOutcomeConfig(
                decision="soft_risk",
                reason="work_outside_workplace",
            ),
            priority=200,
        )
    ]

    result = evaluate_rules(
        world=_build_world(),
        intent=ActionIntent(agent_id="truman", action_type="work"),
        package=_build_package(rules),
    )

    assert result.decision == "soft_risk"
    assert result.primary_rule_id == "working_outside_workplace"
    assert result.reason == "work_outside_workplace"


def test_rule_evaluator_returns_allowed_when_no_rules_match():
    from app.scenario.runtime.rule_evaluator import evaluate_rules

    rules = [
        RuleConfigItem(
            rule_id="night_talk_risk",
            name="Night Talk Risk",
            trigger=RuleTriggerConfig(action_types=["talk"]),
            conditions=[
                RuleConditionConfig(fact="world.time_period", op="eq", value="night"),
            ],
            outcome=RuleOutcomeConfig(decision="soft_risk", reason="night_risk"),
            priority=100,
        )
    ]

    result = evaluate_rules(
        world=_build_world(),
        intent=ActionIntent(agent_id="truman", action_type="rest"),
        package=_build_package(rules),
    )

    assert result.decision == "allowed"
    assert result.primary_rule_id is None
    assert result.matched_rule_ids == []


def test_rule_evaluator_raises_for_unknown_operator():
    from app.scenario.runtime.rule_evaluator import evaluate_rules

    rules = [
        RuleConfigItem(
            rule_id="bad_operator",
            name="Bad Operator",
            trigger=RuleTriggerConfig(action_types=["rest"]),
            conditions=[
                RuleConditionConfig(fact="world.time_period", op="starts_with", value="n"),
            ],
            outcome=RuleOutcomeConfig(decision="soft_risk", reason="bad_op"),
            priority=1,
        )
    ]

    with pytest.raises(ValueError, match="Unsupported operator"):
        evaluate_rules(
            world=_build_world(),
            intent=ActionIntent(agent_id="truman", action_type="rest"),
            package=_build_package(rules),
        )


def test_narrative_world_assets_mark_stranger_night_talk_as_soft_risk():
    from app.scenario.runtime.rule_evaluator import evaluate_rules
    from app.scenario.runtime.world_design import load_world_design_runtime_package

    world = WorldState(
        current_time=datetime(2026, 3, 21, 23, 30, tzinfo=UTC),
        locations={
            "plaza": LocationState(
                id="plaza",
                name="Plaza",
                capacity=4,
                occupants={"truman", "bob"},
                location_type="plaza",
            )
        },
        agents={
            "truman": AgentState(
                id="truman",
                name="Truman",
                location_id="plaza",
                status={"world_role": "truman"},
            ),
            "bob": AgentState(
                id="bob",
                name="Bob",
                location_id="plaza",
                status={"world_role": "cast"},
            ),
        },
        relationship_contexts={
            "truman": {
                "bob": {
                    "familiarity": 0.1,
                    "trust": 0.0,
                    "affinity": 0.0,
                    "relation_type": "stranger",
                    "relationship_level": "stranger",
                }
            }
        },
    )

    result = evaluate_rules(
        world=world,
        intent=ActionIntent(agent_id="truman", action_type="talk", target_agent_id="bob"),
        package=load_world_design_runtime_package("narrative_world", force_reload=True),
    )

    assert result.decision == "soft_risk"
    assert result.primary_rule_id == "late_night_stranger_talk_risk"


def test_narrative_world_assets_allow_family_talk_at_night_without_stranger_risk():
    from app.scenario.runtime.rule_evaluator import evaluate_rules
    from app.scenario.runtime.world_design import load_world_design_runtime_package

    world = WorldState(
        current_time=datetime(2026, 3, 21, 23, 30, tzinfo=UTC),
        locations={
            "home": LocationState(
                id="home",
                name="Home",
                capacity=4,
                occupants={"truman", "spouse"},
                location_type="home",
            )
        },
        agents={
            "truman": AgentState(
                id="truman",
                name="Truman",
                location_id="home",
                status={"world_role": "truman"},
            ),
            "spouse": AgentState(
                id="spouse",
                name="Spouse",
                location_id="home",
                status={"world_role": "cast"},
            ),
        },
        relationship_contexts={
            "truman": {
                "spouse": {
                    "familiarity": 0.95,
                    "trust": 0.9,
                    "affinity": 0.85,
                    "relation_type": "family",
                    "relationship_level": "family",
                }
            }
        },
    )

    result = evaluate_rules(
        world=world,
        intent=ActionIntent(agent_id="truman", action_type="talk", target_agent_id="spouse"),
        package=load_world_design_runtime_package("narrative_world", force_reload=True),
    )

    assert result.decision == "allowed"


def test_narrative_world_assets_mark_shutdown_location_move_as_violation():
    from app.scenario.runtime.rule_evaluator import evaluate_rules
    from app.scenario.runtime.world_design import load_world_design_runtime_package

    world = WorldState(
        current_time=datetime(2026, 3, 21, 10, 0, tzinfo=UTC),
        current_tick=3,
        world_effects={
            "location_shutdowns": [
                {
                    "location_id": "plaza",
                    "start_tick": 1,
                    "end_tick": 6,
                    "message": "Plaza closed",
                }
            ]
        },
        locations={
            "home": LocationState(id="home", name="Home", capacity=4, occupants={"truman"}),
            "plaza": LocationState(id="plaza", name="Plaza", capacity=6, location_type="plaza"),
        },
        agents={
            "truman": AgentState(
                id="truman",
                name="Truman",
                location_id="home",
                status={"world_role": "truman"},
            ),
        },
    )

    result = evaluate_rules(
        world=world,
        intent=ActionIntent(agent_id="truman", action_type="move", target_location_id="plaza"),
        package=load_world_design_runtime_package("narrative_world", force_reload=True),
    )

    assert result.decision == "violates_rule"
    assert result.primary_rule_id == "location_closed_access"
    assert result.reason == "location_closed"


def test_narrative_world_assets_mark_work_in_power_outage_location_as_violation():
    from app.scenario.runtime.rule_evaluator import evaluate_rules
    from app.scenario.runtime.world_design import load_world_design_runtime_package

    world = WorldState(
        current_time=datetime(2026, 3, 21, 14, 0, tzinfo=UTC),
        current_tick=4,
        world_effects={
            "power_outages": [
                {
                    "location_id": "hospital",
                    "start_tick": 2,
                    "end_tick": 8,
                    "message": "Hospital outage",
                }
            ]
        },
        locations={
            "hospital": LocationState(
                id="hospital",
                name="Hospital",
                capacity=8,
                occupants={"meryl"},
                location_type="hospital",
            )
        },
        agents={
            "meryl": AgentState(
                id="meryl",
                name="Meryl",
                location_id="hospital",
                workplace_id="hospital",
                status={"world_role": "cast"},
            ),
        },
    )

    result = evaluate_rules(
        world=world,
        intent=ActionIntent(agent_id="meryl", action_type="work"),
        package=load_world_design_runtime_package("narrative_world", force_reload=True),
    )

    assert result.decision == "violates_rule"
    assert result.primary_rule_id == "power_outage_work_restriction"
    assert result.reason == "power_outage_restriction"
