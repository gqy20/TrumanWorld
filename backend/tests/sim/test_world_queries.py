from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from app.sim.world import AgentState, LocationState, WorldState
from app.sim.world_queries import build_familiarity_map, find_nearby_agent, list_other_occupants


def test_find_nearby_agent_returns_sorted_other_occupant():
    world = WorldState(
        current_time=datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
        locations={
            "square": LocationState(
                id="square",
                name="Square",
                occupants={"truman", "alice", "meryl"},
            )
        },
        agents={
            "truman": AgentState(id="truman", name="Truman", location_id="square"),
            "alice": AgentState(id="alice", name="Alice", location_id="square"),
            "meryl": AgentState(id="meryl", name="Meryl", location_id="square"),
        },
    )

    assert find_nearby_agent(world, "truman", "square") == "alice"
    assert list_other_occupants(world, "truman", "square") == ["alice", "meryl"]


def test_build_familiarity_map_ignores_missing_other_agent_ids():
    relationships = [
        SimpleNamespace(other_agent_id="meryl", familiarity=0.8),
        SimpleNamespace(other_agent_id="alice", familiarity=0.4),
        SimpleNamespace(other_agent_id=None, familiarity=1.0),
    ]

    assert build_familiarity_map(relationships) == {"meryl": 0.8, "alice": 0.4}
