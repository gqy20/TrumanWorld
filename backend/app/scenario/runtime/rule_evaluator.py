"""Minimal rule evaluator for world design runtime assets."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.scenario.runtime.fact_resolver import build_rule_facts, resolve_fact_value
from app.scenario.runtime.world_design_models import (
    RuleConditionConfig,
    RuleConfigItem,
    RuleDecision,
    RuleEvaluationResult,
    WorldDesignRuntimePackage,
)
from app.sim.world import WorldState

if TYPE_CHECKING:
    from app.sim.action_resolver import ActionIntent

_DECISION_PRIORITY: dict[RuleDecision, int] = {
    "impossible": 4,
    "violates_rule": 3,
    "soft_risk": 2,
    "allowed": 1,
}


def evaluate_rules(
    *,
    world: WorldState,
    intent: ActionIntent,
    package: WorldDesignRuntimePackage,
) -> RuleEvaluationResult:
    facts = build_rule_facts(world=world, intent=intent, package=package)
    matched_rules = [
        rule
        for rule in package.rules_config.rules
        if _rule_applies(rule, intent.action_type) and _conditions_match(rule.conditions, facts)
    ]
    if not matched_rules:
        return RuleEvaluationResult(decision="allowed")

    matched_rules.sort(
        key=lambda rule: (rule.priority, _DECISION_PRIORITY[rule.outcome.decision]),
        reverse=True,
    )
    primary_rule = matched_rules[0]
    return RuleEvaluationResult(
        decision=primary_rule.outcome.decision,
        primary_rule_id=primary_rule.rule_id,
        reason=primary_rule.outcome.reason,
        risk_level=primary_rule.outcome.risk_level,
        matched_rule_ids=[rule.rule_id for rule in matched_rules],
    )


def _rule_applies(rule: RuleConfigItem, action_type: str) -> bool:
    action_types = rule.trigger.action_types
    return not action_types or action_type in action_types


def _conditions_match(conditions: list[RuleConditionConfig], facts: dict[str, Any]) -> bool:
    return all(_condition_matches(condition, facts) for condition in conditions)


def _condition_matches(condition: RuleConditionConfig, facts: dict[str, Any]) -> bool:
    left = resolve_fact_value(facts, condition.fact)
    right = (
        resolve_fact_value(facts, condition.value_from)
        if condition.value_from is not None
        else condition.value
    )
    return _apply_operator(condition.op, left, right)


def _apply_operator(op: str, left: Any, right: Any) -> bool:
    if op == "eq":
        return left == right
    if op == "neq":
        return left != right
    if op == "in":
        return left in right
    if op == "not_in":
        return left not in right
    if op == "gt":
        return left > right
    if op == "gte":
        return left >= right
    if op == "lt":
        return left < right
    if op == "lte":
        return left <= right
    if op == "contains":
        return right in left

    msg = f"Unsupported operator: {op}"
    raise ValueError(msg)
