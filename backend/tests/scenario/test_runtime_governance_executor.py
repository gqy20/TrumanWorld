from datetime import UTC, datetime

from app.scenario.runtime.governance_executor import execute_governance
from app.scenario.runtime.world_design_models import (
    PolicyConfig,
    RuleEvaluationResult,
    RulesConfig,
    WorldDesignRuntimePackage,
)
from app.sim.action_resolver import ActionIntent
from app.sim.world import AgentState, LocationState, WorldState


def _build_world() -> WorldState:
    return WorldState(
        current_time=datetime(2026, 3, 21, 23, 30, tzinfo=UTC),
        locations={
            "home": LocationState(id="home", name="Home", capacity=2, occupants={"alice"}),
            "park": LocationState(id="park", name="Park", capacity=4, occupants=set()),
            "cafe": LocationState(id="cafe", name="Cafe", location_type="cafe", occupants=set()),
            "hospital": LocationState(
                id="hospital",
                name="Hospital",
                location_type="hospital",
                occupants=set(),
            ),
        },
        agents={
            "alice": AgentState(id="alice", name="Alice", location_id="home"),
        },
    )


def _build_package(*, inspection_level: str = "medium") -> WorldDesignRuntimePackage:
    return WorldDesignRuntimePackage(
        scenario_id="narrative_world",
        world_config={},
        rules_config=RulesConfig(version=1, rules=[]),
        policy_config=PolicyConfig(
            version=1,
            policy_id="default",
            values={
                "inspection_level": inspection_level,
                "high_attention_locations": ["cafe"],
                "sensitive_locations": ["hospital"],
            },
        ),
        constitution_text="",
    )


def _build_package_with_values(values: dict) -> WorldDesignRuntimePackage:
    merged_values = {
        "inspection_level": "medium",
        "high_attention_locations": ["cafe"],
        "sensitive_locations": ["hospital"],
        **values,
    }
    return WorldDesignRuntimePackage(
        scenario_id="narrative_world",
        world_config={},
        rules_config=RulesConfig(version=1, rules=[]),
        policy_config=PolicyConfig(
            version=1,
            policy_id="default",
            values=merged_values,
        ),
        constitution_text="",
    )


def test_governance_executor_allows_allowed_decision():
    result = execute_governance(
        world=_build_world(),
        intent=ActionIntent(agent_id="alice", action_type="rest"),
        rule_evaluation=RuleEvaluationResult(decision="allowed", reason="rest_allowed"),
        package=_build_package(),
    )

    assert result.decision == "allow"
    assert result.observed is False
    assert result.observation_score == 0.0
    assert result.enforcement_action == "none"


def test_governance_executor_blocks_impossible_decision():
    result = execute_governance(
        world=_build_world(),
        intent=ActionIntent(agent_id="alice", action_type="move", target_location_id="cafe"),
        rule_evaluation=RuleEvaluationResult(decision="impossible", reason="location_full"),
        package=_build_package(),
    )

    assert result.decision == "block"
    assert result.observed is True
    assert result.enforcement_action == "intercept"
    assert result.observation_score == 1.0
    assert result.intervention_score == 1.0


def test_governance_executor_warns_for_soft_risk():
    result = execute_governance(
        world=_build_world(),
        intent=ActionIntent(agent_id="alice", action_type="talk", target_location_id="cafe"),
        rule_evaluation=RuleEvaluationResult(
            decision="soft_risk",
            reason="late_night_talk_risk",
            matched_tags=["social"],
        ),
        package=_build_package(),
    )

    assert result.decision == "warn"
    assert result.observed is True
    assert result.observation_score >= 0.5
    assert "high_attention_location" in result.matched_signals


def test_governance_executor_records_observed_soft_risk_without_strong_intervention_signal():
    result = execute_governance(
        world=_build_world(),
        intent=ActionIntent(agent_id="alice", action_type="talk", target_location_id="park"),
        rule_evaluation=RuleEvaluationResult(
            decision="soft_risk",
            reason="late_night_talk_risk",
            matched_tags=["social"],
        ),
        package=_build_package_with_values(
            {
                "inspection_level": "medium",
                "high_attention_locations": [],
                "warn_intervention_threshold": 0.7,
            }
        ),
    )

    assert result.decision == "record_only"
    assert result.observed is True
    assert result.enforcement_action == "record"
    assert result.observation_score >= 0.5
    assert result.intervention_score < 0.7


def test_governance_executor_warns_for_low_inspection_violation_in_high_attention_location():
    result = execute_governance(
        world=_build_world(),
        intent=ActionIntent(agent_id="alice", action_type="move", target_location_id="cafe"),
        rule_evaluation=RuleEvaluationResult(decision="violates_rule", reason="location_closed"),
        package=_build_package(inspection_level="low"),
    )

    assert result.decision == "warn"
    assert result.observed is True
    assert result.enforcement_action == "warning"


def test_governance_executor_uses_policy_weights_to_turn_low_inspection_violation_into_warning():
    result = execute_governance(
        world=_build_world(),
        intent=ActionIntent(agent_id="alice", action_type="move", target_location_id="park"),
        rule_evaluation=RuleEvaluationResult(decision="violates_rule", reason="location_closed"),
        package=_build_package_with_values(
            {
                "inspection_level": "low",
                "high_attention_locations": [],
                "low_inspection_observation_base": 0.45,
                "violation_observation_bonus": 0.1,
            }
        ),
    )

    assert result.decision == "warn"
    assert result.observed is True
    assert result.enforcement_action == "warning"


def test_governance_executor_allows_unobserved_low_inspection_violation():
    result = execute_governance(
        world=_build_world(),
        intent=ActionIntent(agent_id="alice", action_type="move", target_location_id="park"),
        rule_evaluation=RuleEvaluationResult(decision="violates_rule", reason="location_closed"),
        package=_build_package(inspection_level="low"),
    )

    assert result.decision == "allow"
    assert result.observed is False
    assert result.enforcement_action == "none"
    assert result.observation_score < 0.5
    assert result.intervention_score < 0.75


def test_governance_executor_blocks_subject_violation_even_when_inspection_low():
    result = execute_governance(
        world=_build_world(),
        intent=ActionIntent(agent_id="alice", action_type="talk", target_location_id="cafe"),
        rule_evaluation=RuleEvaluationResult(
            decision="violates_rule",
            reason="subject_contact_violation",
            matched_tags=["subject"],
        ),
        package=_build_package(inspection_level="low"),
    )

    assert result.decision == "block"
    assert result.observed is True
    assert "subject" in result.matched_signals
