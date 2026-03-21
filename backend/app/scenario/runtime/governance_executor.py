"""Deterministic governance execution for world rule outcomes."""

from __future__ import annotations

from app.scenario.runtime.world_design_models import (
    GovernanceExecutionResult,
    RuleEvaluationResult,
    WorldDesignRuntimePackage,
)
from app.sim.world import WorldState

if False:  # pragma: no cover
    from app.sim.action_resolver import ActionIntent


def execute_governance(
    *,
    world: WorldState,
    intent: "ActionIntent",
    rule_evaluation: RuleEvaluationResult | None,
    package: WorldDesignRuntimePackage,
) -> GovernanceExecutionResult:
    if rule_evaluation is None:
        return GovernanceExecutionResult(
            decision="allow",
            reason="no_rule_evaluation",
            enforcement_action="none",
            observed=False,
            observation_score=0.0,
            intervention_score=0.0,
        )

    if rule_evaluation.decision == "allowed":
        return GovernanceExecutionResult(
            decision="allow",
            reason=rule_evaluation.reason or "allowed",
            enforcement_action="none",
            observed=False,
            observation_score=0.0,
            intervention_score=0.0,
        )

    if rule_evaluation.decision == "impossible":
        return GovernanceExecutionResult(
            decision="block",
            reason=rule_evaluation.reason or "impossible",
            enforcement_action="intercept",
            observed=True,
            observation_score=1.0,
            intervention_score=1.0,
            matched_signals=["physical_or_system_constraint"],
        )

    policy_values = package.policy_config.values or {}
    inspection_level = str(policy_values.get("inspection_level") or "medium").lower()
    high_attention_locations = _normalize_str_list(policy_values.get("high_attention_locations"))
    sensitive_locations = _normalize_str_list(policy_values.get("sensitive_locations"))

    signals = list(rule_evaluation.matched_tags)
    agent = world.get_agent(intent.agent_id)
    current_location_id = intent.target_location_id or (agent.location_id if agent is not None else None)
    if current_location_id in high_attention_locations:
        signals.append("high_attention_location")
    if current_location_id in sensitive_locations:
        signals.append("sensitive_location")

    actor_attention_score = 0.0
    warning_count = 0
    observation_count = 0
    if agent is not None and isinstance(agent.status, dict):
        actor_attention_score = float(agent.status.get("governance_attention_score", 0.0) or 0.0)
        warning_count = int(agent.status.get("warning_count", 0) or 0)
        observation_count = int(agent.status.get("observation_count", 0) or 0)
    observation_score = _compute_observation_score(
        inspection_level=inspection_level,
        signals=signals,
        actor_attention_score=actor_attention_score,
        warning_count=warning_count,
        observation_count=observation_count,
        rule_evaluation=rule_evaluation,
        policy_values=policy_values,
    )
    intervention_score = _compute_intervention_score(
        observation_score=observation_score,
        inspection_level=inspection_level,
        signals=signals,
        warning_count=warning_count,
        observation_count=observation_count,
        rule_evaluation=rule_evaluation,
        policy_values=policy_values,
    )
    observation_threshold = _get_float(policy_values, "observation_threshold", 0.5)
    warn_threshold = _get_float(policy_values, "warn_intervention_threshold", 0.65)
    block_threshold = _get_float(policy_values, "block_intervention_threshold", 0.85)
    observed = observation_score >= observation_threshold
    normalized_signals = sorted(set(signals))

    if not observed:
        return GovernanceExecutionResult(
            decision="allow",
            reason=rule_evaluation.reason or "not_observed",
            enforcement_action="none",
            observed=False,
            observation_score=observation_score,
            intervention_score=intervention_score,
            matched_signals=normalized_signals,
        )

    if rule_evaluation.decision == "soft_risk":
        if intervention_score < warn_threshold:
            return GovernanceExecutionResult(
                decision="record_only",
                reason=rule_evaluation.reason or "soft_risk_recorded",
                enforcement_action="record",
                observed=True,
                observation_score=observation_score,
                intervention_score=intervention_score,
                matched_signals=normalized_signals,
            )
        return GovernanceExecutionResult(
            decision="warn",
            reason=rule_evaluation.reason or "soft_risk_warning",
            enforcement_action="warning",
            observed=True,
            observation_score=observation_score,
            intervention_score=intervention_score,
            matched_signals=normalized_signals,
        )

    if "subject" in signals or "sensitive_location" in signals:
        return GovernanceExecutionResult(
            decision="block",
            reason=rule_evaluation.reason or "policy_blocked",
            enforcement_action="intercept",
            observed=True,
            observation_score=observation_score,
            intervention_score=max(intervention_score, block_threshold),
            matched_signals=normalized_signals,
        )

    if intervention_score < warn_threshold:
        return GovernanceExecutionResult(
            decision="record_only",
            reason=rule_evaluation.reason or "policy_recorded",
            enforcement_action="record",
            observed=True,
            observation_score=observation_score,
            intervention_score=intervention_score,
            matched_signals=normalized_signals,
        )

    if intervention_score < block_threshold:
        return GovernanceExecutionResult(
            decision="warn",
            reason=rule_evaluation.reason or "policy_warning",
            enforcement_action="warning",
            observed=True,
            observation_score=observation_score,
            intervention_score=intervention_score,
            matched_signals=normalized_signals,
        )

    return GovernanceExecutionResult(
        decision="block",
        reason=rule_evaluation.reason or "policy_blocked",
        enforcement_action="intercept",
        observed=True,
        observation_score=observation_score,
        intervention_score=intervention_score,
        matched_signals=normalized_signals,
    )


def _normalize_str_list(value: object) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {item for item in value if isinstance(item, str)}


def _compute_observation_score(
    *,
    inspection_level: str,
    signals: list[str],
    actor_attention_score: float,
    warning_count: int,
    observation_count: int,
    rule_evaluation: RuleEvaluationResult,
    policy_values: dict[str, object],
) -> float:
    base_defaults = {
        "low": 0.2,
        "medium": 0.55,
        "high": 0.85,
    }
    base = _get_float(
        policy_values,
        f"{inspection_level}_inspection_observation_base",
        base_defaults.get(inspection_level, 0.55),
    )

    score = base
    unique_signals = set(signals)
    if "high_attention_location" in unique_signals:
        score += _get_float(policy_values, "high_attention_observation_bonus", 0.3)
    if "sensitive_location" in unique_signals:
        score += _get_float(policy_values, "sensitive_location_observation_bonus", 0.25)
    if "subject" in unique_signals:
        score += _get_float(policy_values, "subject_observation_bonus", 0.3)

    if actor_attention_score >= 0.8:
        score += _get_float(policy_values, "high_attention_score_observation_bonus", 0.2)
    elif actor_attention_score >= 0.5:
        score += _get_float(policy_values, "elevated_attention_score_observation_bonus", 0.12)
    elif actor_attention_score >= 0.2:
        score += _get_float(policy_values, "low_attention_score_observation_bonus", 0.05)

    if rule_evaluation.decision == "soft_risk":
        score += _get_float(policy_values, "soft_risk_observation_bonus", 0.05)
    elif rule_evaluation.decision == "violates_rule":
        score += _get_float(policy_values, "violation_observation_bonus", 0.1)

    if rule_evaluation.risk_level == "medium":
        score += _get_float(policy_values, "medium_risk_observation_bonus", 0.05)
    elif rule_evaluation.risk_level == "high":
        score += _get_float(policy_values, "high_risk_observation_bonus", 0.1)

    score += max(0, observation_count) * _get_float(
        policy_values, "repeat_observation_bonus_per_record", 0.0
    )
    score += max(0, warning_count) * _get_float(
        policy_values, "repeat_observation_bonus_per_warning", 0.0
    )

    return round(min(1.0, score), 6)


def _compute_intervention_score(
    *,
    observation_score: float,
    inspection_level: str,
    signals: list[str],
    warning_count: int,
    observation_count: int,
    rule_evaluation: RuleEvaluationResult,
    policy_values: dict[str, object],
) -> float:
    score = observation_score + _get_float(
        policy_values,
        f"{inspection_level}_inspection_intervention_bonus",
        0.0,
    )
    unique_signals = set(signals)

    if rule_evaluation.decision == "violates_rule":
        score += _get_float(policy_values, "violation_intervention_bonus", 0.2)
    elif rule_evaluation.decision == "soft_risk":
        score += _get_float(policy_values, "soft_risk_intervention_bonus", 0.05)

    if rule_evaluation.risk_level == "medium":
        score += _get_float(policy_values, "medium_risk_intervention_bonus", 0.05)
    elif rule_evaluation.risk_level == "high":
        score += _get_float(policy_values, "high_risk_intervention_bonus", 0.1)

    if "subject" in unique_signals or "sensitive_location" in unique_signals:
        score += _get_float(policy_values, "strong_signal_intervention_bonus", 0.15)

    if inspection_level == "high":
        score += _get_float(policy_values, "high_inspection_intervention_bonus", 0.05)

    score += max(0, observation_count) * _get_float(
        policy_values, "repeat_observation_intervention_bonus_per_record", 0.0
    )
    score += max(0, warning_count) * _get_float(
        policy_values, "repeat_warning_intervention_bonus_per_warning", 0.0
    )

    return round(min(1.0, score), 6)


def _get_float(policy_values: dict[str, object], key: str, default: float) -> float:
    value = policy_values.get(key, default)
    return float(value) if isinstance(value, (int, float)) else default
