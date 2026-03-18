"""Strategy condition engine for Director Agent.

This module provides a rule engine that evaluates strategy conditions
based on configuration from director.yml.
"""

from __future__ import annotations

from typing import Any

from app.director.observer import DirectorAssessment
from app.infra.logging import get_logger

logger = get_logger(__name__)


class StrategyConditionEngine:
    """Engine for evaluating strategy conditions from configuration.

    Supports condition types:
    - threshold: Compare metric against a threshold value
    - trend: Check if a trend matches expected value
    - in: Check if metric is in a list of values
    - eq: Check if metric equals a value
    """

    def evaluate(self, condition: dict[str, Any], assessment: DirectorAssessment) -> bool:
        """Evaluate a condition against the current assessment.

        Args:
            condition: Condition configuration from director.yml
            assessment: Current world state assessment

        Returns:
            True if condition is met, False otherwise
        """
        condition_type = condition.get("type", "threshold")
        metric_name = condition.get("metric")
        operator = condition.get("operator", "gte")
        expected_value = condition.get("value")

        # Get metric value from assessment
        metric_value = self._get_metric(metric_name, assessment)
        if metric_value is None:
            logger.debug(f"Metric {metric_name} not found in assessment")
            return False

        # Evaluate based on condition type
        if condition_type == "threshold":
            return self._evaluate_threshold(metric_value, operator, expected_value)
        elif condition_type == "trend":
            return self._evaluate_trend(metric_value, operator, expected_value)
        elif condition_type == "in":
            return self._evaluate_in(metric_value, expected_value)
        elif condition_type == "eq":
            return self._evaluate_eq(metric_value, expected_value)
        else:
            logger.warning(f"Unknown condition type: {condition_type}")
            return False

    def _get_metric(self, metric_name: str, assessment: DirectorAssessment) -> Any:
        """Get metric value from assessment by name."""
        metric_map = {
            "truman_isolation_ticks": assessment.truman_isolation_ticks,
            "suspicion_level": assessment.suspicion_level,
            "suspicion_trend": assessment.suspicion_trend.trend_type
            if assessment.suspicion_trend
            else None,
            "continuity_risk": assessment.continuity_risk,
            "recent_rejections": assessment.recent_rejections,
            "subject_alert_score": assessment.subject_alert_score,
            "truman_suspicion_score": assessment.subject_alert_score,
        }
        return metric_map.get(metric_name)

    def _evaluate_threshold(self, value: Any, operator: str, threshold: Any) -> bool:
        """Evaluate threshold condition."""
        try:
            value = float(value)
            threshold = float(threshold)
        except (TypeError, ValueError):
            return False

        operators = {
            "gte": lambda v, t: v >= t,
            "gt": lambda v, t: v > t,
            "lte": lambda v, t: v <= t,
            "lt": lambda v, t: v < t,
            "eq": lambda v, t: v == t,
            "ne": lambda v, t: v != t,
        }

        op_func = operators.get(operator)
        if op_func is None:
            logger.warning(f"Unknown operator: {operator}")
            return False

        return op_func(value, threshold)

    def _evaluate_trend(self, trend_type: str | None, operator: str, expected: str) -> bool:
        """Evaluate trend condition."""
        if trend_type is None:
            return False

        if operator == "eq":
            return trend_type == expected
        elif operator == "ne":
            return trend_type != expected
        else:
            logger.warning(f"Unknown trend operator: {operator}")
            return False

    def _evaluate_in(self, value: Any, allowed_values: list[Any]) -> bool:
        """Evaluate 'in' condition."""
        if not isinstance(allowed_values, list):
            logger.warning(f"Expected list for 'in' condition, got {type(allowed_values)}")
            return False
        return value in allowed_values

    def _evaluate_eq(self, value: Any, expected: Any) -> bool:
        """Evaluate equality condition."""
        return value == expected


class StrategyExecutor:
    """Executor for configured strategies.

    Uses StrategyConditionEngine to evaluate conditions and build DirectorPlan
    from strategy configuration.
    """

    def __init__(self) -> None:
        self._condition_engine = StrategyConditionEngine()

    def evaluate_strategies(
        self,
        strategies: dict[str, Any],
        assessment: DirectorAssessment,
        recent_goals: set[str],
        subject_agent_id: str | None,
        primary_cast_id: str | None,
    ) -> dict[str, Any] | None:
        """Evaluate all strategies and return the first triggered one.

        Strategies are evaluated in order of priority:
        1. critical priority
        2. high priority
        3. normal priority
        4. advisory/low priority

        Args:
            strategies: Strategy configurations from director.yml
            assessment: Current world state assessment
            recent_goals: Recently used goals to avoid repetition
            subject_agent_id: Primary subject agent ID
            primary_cast_id: Primary cast agent ID for intervention

        Returns:
            Triggered strategy config or None
        """
        if not strategies or primary_cast_id is None:
            return None

        # Priority order
        priority_order = ["critical", "high", "normal", "advisory", "low"]

        # Group strategies by priority
        strategies_by_priority: dict[str, list[tuple[str, Any]]] = {}
        for strategy_id, strategy_config in strategies.items():
            action = strategy_config.action
            priority = (
                action.get("priority", "normal")
                if isinstance(action, dict)
                else getattr(action, "priority", "normal")
            )

            # Skip if recently used
            scene_goal = (
                action.get("scene_goal", strategy_id)
                if isinstance(action, dict)
                else getattr(action, "scene_goal", strategy_id)
            )
            if scene_goal in recent_goals:
                continue

            if priority not in strategies_by_priority:
                strategies_by_priority[priority] = []
            strategies_by_priority[priority].append((strategy_id, strategy_config))

        # Evaluate in priority order
        for priority in priority_order:
            if priority not in strategies_by_priority:
                continue

            for strategy_id, strategy_config in strategies_by_priority[priority]:
                condition = strategy_config.condition

                if self._condition_engine.evaluate(condition, assessment):
                    logger.debug(f"Strategy '{strategy_id}' triggered (priority: {priority})")
                    return {
                        "strategy_id": strategy_id,
                        "config": strategy_config,
                        "subject_agent_id": subject_agent_id,
                        "primary_cast_id": primary_cast_id,
                    }

        return None

    def build_plan_from_strategy(self, triggered: dict[str, Any]) -> dict[str, Any] | None:
        """Build a DirectorPlan-compatible dict from triggered strategy.

        Args:
            triggered: Triggered strategy info from evaluate_strategies

        Returns:
            Dict with DirectorPlan fields
        """
        if triggered is None:
            return None

        strategy_id = triggered["strategy_id"]
        config = triggered["config"]
        action = config.action

        # Build reason from condition
        condition = config.condition
        metric = (
            condition.get("metric", "unknown")
            if isinstance(condition, dict)
            else getattr(condition, "metric", "unknown")
        )
        operator = (
            condition.get("operator", "eq")
            if isinstance(condition, dict)
            else getattr(condition, "operator", "eq")
        )
        value = (
            condition.get("value", "unknown")
            if isinstance(condition, dict)
            else getattr(condition, "value", "unknown")
        )

        config_name = (
            config.name
            if hasattr(config, "name")
            else config.get("name", strategy_id)
            if isinstance(config, dict)
            else strategy_id
        )
        reason_map = {
            "truman_isolation_ticks": f"Truman 已经连续独处较长时间，触发 '{config_name}' 策略",
            "suspicion_trend": f"怀疑度趋势为 {value}，触发 '{config_name}' 策略",
            "suspicion_level": f"怀疑度等级为 {value}，触发 '{config_name}' 策略",
            "continuity_risk": f"连续性风险为 {value}，触发 '{config_name}' 策略",
            "recent_rejections": f"连续被拒绝 {value} 次，触发 '{config_name}' 策略",
        }
        reason = reason_map.get(
            metric, f"条件满足（{metric} {operator} {value}），触发 '{config_name}' 策略"
        )

        # Handle action as dict or dataclass
        if isinstance(action, dict):
            scene_goal = action.get("scene_goal", strategy_id)
            priority = action.get("priority", "normal")
            urgency = action.get("urgency", "advisory")
            cooldown_ticks = action.get("cooldown_ticks", 3)
        else:
            scene_goal = getattr(action, "scene_goal", strategy_id)
            priority = getattr(action, "priority", "normal")
            urgency = getattr(action, "urgency", "advisory")
            cooldown_ticks = getattr(action, "cooldown_ticks", 3)

        message_hint = (
            config.message_hint
            if hasattr(config, "message_hint")
            else config.get("message_hint", "")
            if isinstance(config, dict)
            else ""
        )

        return {
            "scene_goal": scene_goal,
            "target_agent_ids": [triggered["primary_cast_id"]],
            "priority": priority,
            "urgency": urgency,
            "message_hint": message_hint,
            "target_agent_id": triggered["subject_agent_id"],
            "reason": reason,
            "cooldown_ticks": cooldown_ticks,
        }
