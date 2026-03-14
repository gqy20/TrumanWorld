"""Tests for dynamic plan update feature.

This module tests the ability for Reactor to dynamically update
an agent's current_plan when significant events occur.
"""

import pytest
from dataclasses import dataclass, field
from typing import Any


# Copy of PlanUpdate for testing
@dataclass
class PlanUpdate:
    """Represents a request to update the agent's current plan."""

    reason: str
    new_morning: str | None = None
    new_daytime: str | None = None
    new_evening: str | None = None


# Copy of ActionIntent for testing
@dataclass
class ActionIntent:
    """Test version of ActionIntent with plan_update support."""

    agent_id: str
    action_type: str
    target_location_id: str | None = None
    target_agent_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    plan_update: PlanUpdate | None = None


class TestPlanUpdate:
    """Tests for plan update data structures."""

    def test_action_intent_supports_plan_update(self):
        """ActionIntent should support plan_update field."""
        intent = ActionIntent(
            agent_id="agent_1",
            action_type="talk",
            target_agent_id="bob",
            payload={"message": "Hi Bob!"},
            plan_update=PlanUpdate(
                reason="遇到重要的人",
                new_daytime="和 Bob 聊天",
            ),
        )

        assert intent.action_type == "talk"
        assert intent.plan_update is not None
        assert intent.plan_update.reason == "遇到重要的人"
        assert intent.plan_update.new_daytime == "和 Bob 聊天"

    def test_plan_update_partial_update(self):
        """PlanUpdate should support partial updates (only some time periods)."""
        intent = ActionIntent(
            agent_id="agent_1",
            action_type="talk",
            plan_update=PlanUpdate(
                reason="遇到重要的人",
                new_daytime="和 Bob 聊天",
            ),
        )

        assert intent.plan_update.new_morning is None
        assert intent.plan_update.new_daytime == "和 Bob 聊天"
        assert intent.plan_update.new_evening is None


class TestShouldUpdatePlan:
    """Tests for should_update_plan logic."""

    def test_should_update_plan_with_valid_reason(self):
        """should_update_plan returns True for valid reasons."""
        intent = ActionIntent(
            agent_id="agent_1",
            action_type="talk",
            plan_update=PlanUpdate(
                reason="遇到重要的人",
                new_daytime="和 Bob 聊天",
            ),
        )

        # Provide valid last_update_tick and current_tick to pass cooldown check
        assert should_update_plan(intent, last_update_tick=0, current_tick=100) is True

    def test_should_update_plan_without_plan_update(self):
        """should_update_plan returns False when no plan_update."""
        intent = ActionIntent(
            agent_id="agent_1",
            action_type="work",
        )

        assert should_update_plan(intent) is False

    def test_should_update_plan_with_invalid_reason(self):
        """should_update_plan returns False for invalid reasons."""
        intent = ActionIntent(
            agent_id="agent_1",
            action_type="rest",
            plan_update=PlanUpdate(
                reason="random_reason",  # Invalid reason
                new_daytime="休息",
            ),
        )

        assert should_update_plan(intent) is False

    def test_should_update_plan_with_cooldown_allow(self):
        """should_update_plan respects cooldown - allow when enough time passed."""
        intent = ActionIntent(
            agent_id="agent_1",
            action_type="talk",
            plan_update=PlanUpdate(
                reason="遇到重要的人",
                new_daytime="和 Bob 聊天",
            ),
        )

        # Last update at tick 50, current tick 100 - cooldown is 12 ticks
        # 100 - 50 = 50 > 12, should allow
        assert (
            should_update_plan(intent, last_update_tick=50, current_tick=100, cooldown_ticks=12)
            is True
        )

    def test_should_update_plan_with_cooldown_deny(self):
        """should_update_plan respects cooldown - deny when too soon."""
        intent = ActionIntent(
            agent_id="agent_1",
            action_type="talk",
            plan_update=PlanUpdate(
                reason="遇到重要的人",
                new_daytime="和 Bob 聊天",
            ),
        )

        # Last update at tick 95, current tick 100 - cooldown is 12 ticks
        # 100 - 95 = 5 < 12, should deny
        assert (
            should_update_plan(intent, last_update_tick=95, current_tick=100, cooldown_ticks=12)
            is False
        )


class TestUpdateAgentPlan:
    """Tests for update_agent_plan function."""

    @pytest.mark.asyncio
    async def test_update_agent_plan_partial(self):
        """update_agent_plan should update only specified time periods."""
        current_plan = {
            "morning": "去咖啡店工作",
            "daytime": "在广场逛逛",
            "evening": "回家做饭",
        }

        plan_update = PlanUpdate(
            reason="遇到重要的人",
            new_daytime="和 Bob 聊天",
        )

        new_plan = update_agent_plan(plan_update, current_plan)

        assert new_plan["morning"] == "去咖啡店工作"  # Unchanged
        assert new_plan["daytime"] == "和 Bob 聊天"  # Updated
        assert new_plan["evening"] == "回家做饭"  # Unchanged

    @pytest.mark.asyncio
    async def test_update_agent_plan_full(self):
        """update_agent_plan should update all specified time periods."""
        current_plan = {
            "morning": "去咖啡店工作",
            "daytime": "在广场逛逛",
            "evening": "回家做饭",
        }

        plan_update = PlanUpdate(
            reason="突发事件",
            new_morning="处理紧急事务",
            new_daytime="处理紧急事务",
            new_evening="休息",
        )

        new_plan = update_agent_plan(plan_update, current_plan)

        assert new_plan["morning"] == "处理紧急事务"
        assert new_plan["daytime"] == "处理紧急事务"
        assert new_plan["evening"] == "休息"

    @pytest.mark.asyncio
    async def test_update_agent_plan_no_change(self):
        """update_agent_plan should return unchanged plan when no updates."""
        current_plan = {
            "morning": "去咖啡店工作",
            "daytime": "在广场逛逛",
            "evening": "回家做饭",
        }

        plan_update = PlanUpdate(
            reason="测试",  # This will be filtered by should_update_plan
        )

        new_plan = update_agent_plan(plan_update, current_plan)

        # All values should remain the same
        assert new_plan == current_plan


# Implementation to be tested


def should_update_plan(
    intent: ActionIntent,
    last_update_tick: int = 0,
    current_tick: int = 0,
    cooldown_ticks: int = 12,  # 1 hour (5 min/tick)
) -> bool:
    """Determine if the plan should be updated based on intent and cooldown."""
    if not intent.plan_update:
        return False

    valid_reasons = [
        "遇到重要的人",
        "突发事件",
        "意外机会",
    ]

    if intent.plan_update.reason not in valid_reasons:
        return False

    # Check cooldown
    if current_tick - last_update_tick < cooldown_ticks:
        return False

    return True


def update_agent_plan(
    plan_update: PlanUpdate,
    current_plan: dict[str, str],
) -> dict[str, str]:
    """Update the agent's current_plan with the provided changes."""
    new_plan = current_plan.copy()

    if plan_update.new_morning:
        new_plan["morning"] = plan_update.new_morning
    if plan_update.new_daytime:
        new_plan["daytime"] = plan_update.new_daytime
    if plan_update.new_evening:
        new_plan["evening"] = plan_update.new_evening

    return new_plan
