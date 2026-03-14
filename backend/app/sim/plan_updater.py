"""Plan update logic for dynamic plan modification.

This module provides functions to:
- Determine if a plan should be updated (with cooldown)
- Apply plan updates
- Log plan changes
"""

from __future__ import annotations

from app.sim.action_resolver import ActionIntent, PlanUpdate

# Valid reasons for plan updates
VALID_PLAN_UPDATE_REASONS = [
    "遇到重要的人",
    "突发事件",
    "意外机会",
]

# Default cooldown: 12 ticks = 1 hour (assuming 5 min/tick)
DEFAULT_COOLDOWN_TICKS = 12


def should_update_plan(
    intent: ActionIntent,
    last_update_tick: int = 0,
    current_tick: int = 0,
    cooldown_ticks: int = DEFAULT_COOLDOWN_TICKS,
) -> bool:
    """Determine if the plan should be updated based on intent and cooldown.

    Args:
        intent: The action intent containing plan_update request
        last_update_tick: The tick number when the plan was last updated
        current_tick: The current tick number
        cooldown_ticks: Minimum ticks between updates

    Returns:
        True if the plan should be updated, False otherwise
    """
    if not intent.plan_update:
        return False

    # Check if reason is valid
    if intent.plan_update.reason not in VALID_PLAN_UPDATE_REASONS:
        return False

    # Check cooldown (skip if last_update_tick is 0, meaning no previous update)
    return not (last_update_tick > 0 and (current_tick - last_update_tick) < cooldown_ticks)


def update_agent_plan(
    plan_update: PlanUpdate,
    current_plan: dict[str, str],
) -> dict[str, str]:
    """Update the agent's current_plan with the provided changes.

    Only updates the time periods that are specified in plan_update.
    Other time periods remain unchanged.

    Args:
        plan_update: The plan update request
        current_plan: The current plan to update

    Returns:
        The updated plan
    """
    new_plan = current_plan.copy()

    if plan_update.new_morning:
        new_plan["morning"] = plan_update.new_morning
    if plan_update.new_daytime:
        new_plan["daytime"] = plan_update.new_daytime
    if plan_update.new_evening:
        new_plan["evening"] = plan_update.new_evening

    return new_plan


def is_valid_plan_update_reason(reason: str) -> bool:
    """Check if a reason is valid for plan update."""
    return reason in VALID_PLAN_UPDATE_REASONS
