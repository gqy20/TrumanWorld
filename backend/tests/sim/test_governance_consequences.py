from datetime import datetime

from app.scenario.runtime.world_design_models import GovernanceExecutionResult
from app.sim.action_resolver import ActionResult
from app.sim.governance_consequences import (
    apply_governance_attention_decay,
    apply_governance_consequences,
)
from app.sim.world import AgentState, WorldState


def _build_world() -> WorldState:
    return WorldState(
        current_time=datetime(2026, 3, 7, 8, 0, 0),
        agents={
            "alice": AgentState(
                id="alice",
                name="Alice",
                location_id="home",
                status={},
            )
        },
        locations={},
    )


def test_apply_governance_consequences_warn_updates_status():
    world = _build_world()
    result = ActionResult(
        accepted=True,
        action_type="move",
        reason="accepted",
        event_payload={"agent_id": "alice"},
        governance_execution=GovernanceExecutionResult(
            decision="warn",
            reason="location_closed",
            enforcement_action="warning",
        ),
    )

    apply_governance_consequences(
        world,
        result,
        policy_values={"warn_attention_delta": 0.08, "attention_score_cap": 1.0},
    )

    assert world.agents["alice"].status["warning_count"] == 1
    assert world.agents["alice"].status["governance_attention_score"] == 0.08


def test_apply_governance_consequences_block_adds_stronger_attention():
    world = _build_world()
    world.agents["alice"].status = {"warning_count": 1, "governance_attention_score": 0.2}
    result = ActionResult(
        accepted=False,
        action_type="move",
        reason="location_closed",
        event_payload={"agent_id": "alice"},
        governance_execution=GovernanceExecutionResult(
            decision="block",
            reason="location_closed",
            enforcement_action="intercept",
        ),
    )

    apply_governance_consequences(
        world,
        result,
        policy_values={"block_attention_delta": 0.25, "attention_score_cap": 1.0},
    )

    assert world.agents["alice"].status["warning_count"] == 2
    assert world.agents["alice"].status["governance_attention_score"] == 0.45


def test_apply_governance_consequences_caps_attention_score():
    world = _build_world()
    world.agents["alice"].status = {"warning_count": 3, "governance_attention_score": 0.95}
    result = ActionResult(
        accepted=False,
        action_type="move",
        reason="location_closed",
        event_payload={"agent_id": "alice"},
        governance_execution=GovernanceExecutionResult(
            decision="block",
            reason="location_closed",
            enforcement_action="intercept",
        ),
    )

    apply_governance_consequences(
        world,
        result,
        policy_values={"block_attention_delta": 0.15, "attention_score_cap": 0.97},
    )

    assert world.agents["alice"].status["warning_count"] == 4
    assert world.agents["alice"].status["governance_attention_score"] == 0.97


def test_apply_governance_consequences_ignores_allow():
    world = _build_world()
    result = ActionResult(
        accepted=True,
        action_type="rest",
        reason="accepted",
        event_payload={"agent_id": "alice"},
        governance_execution=GovernanceExecutionResult(
            decision="allow",
            reason="rest_allowed",
            enforcement_action="none",
        ),
    )

    apply_governance_consequences(world, result)

    assert world.agents["alice"].status == {}


def test_apply_governance_attention_decay_reduces_attention_by_day():
    world = _build_world()
    world.agents["alice"].status = {"warning_count": 2, "governance_attention_score": 0.6}

    apply_governance_attention_decay(
        world,
        days_elapsed=2,
        policy_values={"attention_decay_per_day": 0.1},
    )

    assert world.agents["alice"].status["warning_count"] == 2
    assert world.agents["alice"].status["governance_attention_score"] == 0.4


def test_apply_governance_attention_decay_never_drops_below_zero():
    world = _build_world()
    world.agents["alice"].status = {"governance_attention_score": 0.04}

    apply_governance_attention_decay(
        world,
        days_elapsed=1,
        policy_values={"attention_decay_per_day": 0.1},
    )

    assert world.agents["alice"].status["governance_attention_score"] == 0.0
