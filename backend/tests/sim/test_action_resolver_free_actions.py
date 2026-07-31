"""Action resolver boundary tests for supported and unsupported actions."""

from datetime import datetime

import pytest

from app.sim.action_resolver import ActionIntent, ActionResolver
from app.sim.world import AgentState, LocationState, WorldState


def _build_world() -> WorldState:
    return WorldState(
        current_time=datetime(2026, 3, 7, 8, 0, 0),
        agents={
            "alice": AgentState(id="alice", name="Alice", location_id="cafe", status={}),
            "bob": AgentState(id="bob", name="Bob", location_id="cafe", status={}),
        },
        locations={
            "cafe": LocationState(
                id="cafe",
                name="Cafe",
                location_type="cafe",
                capacity=10,
            ),
            "home": LocationState(id="home", name="Home", location_type="residence"),
        },
    )


@pytest.mark.parametrize(
    "action_type",
    ["trade", "gift", "craft", "open_business", "lend", "negotiate"],
)
def test_unsupported_action_is_rejected(action_type: str) -> None:
    world = _build_world()
    intent = ActionIntent(
        agent_id="alice",
        action_type=action_type,
        target_agent_id="bob",
        payload={"item": "coffee", "price": 30},
    )

    result = ActionResolver().resolve(world, intent)

    assert result.accepted is False
    assert result.reason == "unsupported_action"
    assert result.event_payload == {
        "agent_id": "alice",
        "location_id": "cafe",
        "target_agent_id": "bob",
        "item": "coffee",
        "price": 30,
    }


def test_unsupported_action_for_missing_agent_preserves_missing_agent_error() -> None:
    result = ActionResolver().resolve(
        _build_world(),
        ActionIntent(agent_id="missing", action_type="trade"),
    )

    assert result.accepted is False
    assert result.reason == "agent_not_found"


def test_standard_move_action_still_works() -> None:
    result = ActionResolver().resolve(
        _build_world(),
        ActionIntent(agent_id="alice", action_type="move", target_location_id="home"),
    )

    assert result.accepted is True
    assert result.event_payload["from_location_id"] == "cafe"
    assert result.event_payload["to_location_id"] == "home"


def test_standard_talk_action_still_works() -> None:
    result = ActionResolver().resolve(
        _build_world(),
        ActionIntent(
            agent_id="alice",
            action_type="talk",
            target_agent_id="bob",
            payload={"message": "Hello Bob!"},
        ),
    )

    assert result.accepted is True
    assert result.event_payload["conversation_event_type"] == "speech"


@pytest.mark.parametrize("action_type", ["work", "rest"])
def test_standard_non_targeted_action_still_works(action_type: str) -> None:
    world = _build_world()
    if action_type == "work":
        world.agents["alice"].workplace_id = "cafe"

    result = ActionResolver().resolve(
        world,
        ActionIntent(agent_id="alice", action_type=action_type),
    )

    assert result.accepted is True
