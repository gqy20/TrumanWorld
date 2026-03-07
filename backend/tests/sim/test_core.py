from datetime import datetime

from app.sim.action_resolver import ActionIntent, ActionResolver
from app.sim.runner import SimulationRunner
from app.sim.world import AgentState, LocationState, WorldState


def build_world() -> WorldState:
    home = LocationState(id="home", name="Home", capacity=2, occupants={"alice"})
    cafe = LocationState(id="cafe", name="Cafe", capacity=2, occupants={"bob"})
    park = LocationState(id="park", name="Park", capacity=1, occupants=set())
    agents = {
        "alice": AgentState(id="alice", name="Alice", location_id="home", status={"energy": 0.8}),
        "bob": AgentState(id="bob", name="Bob", location_id="cafe", status={"energy": 0.7}),
    }
    return WorldState(
        current_time=datetime(2026, 3, 7, 8, 0, 0),
        tick_minutes=5,
        locations={"home": home, "cafe": cafe, "park": park},
        agents=agents,
    )


def test_action_resolver_accepts_valid_move():
    world = build_world()
    resolver = ActionResolver()

    result = resolver.resolve(
        world,
        ActionIntent(agent_id="alice", action_type="move", target_location_id="park"),
    )

    assert result.accepted is True
    assert result.event_payload["to_location_id"] == "park"
    assert world.agents["alice"].location_id == "park"


def test_action_resolver_rejects_move_to_full_location():
    world = build_world()
    world.locations["park"].occupants.add("charlie")
    resolver = ActionResolver()

    result = resolver.resolve(
        world,
        ActionIntent(agent_id="alice", action_type="move", target_location_id="park"),
    )

    assert result.accepted is False
    assert result.reason == "location_full"
    assert world.agents["alice"].location_id == "home"


def test_action_resolver_rejects_talk_if_agents_are_apart():
    world = build_world()
    resolver = ActionResolver()

    result = resolver.resolve(
        world,
        ActionIntent(agent_id="alice", action_type="talk", target_agent_id="bob"),
    )

    assert result.accepted is False
    assert result.reason == "target_not_nearby"


def test_simulation_runner_advances_tick_and_collects_results():
    world = build_world()
    runner = SimulationRunner(world)

    result = runner.tick(
        [
            ActionIntent(agent_id="alice", action_type="move", target_location_id="park"),
            ActionIntent(agent_id="bob", action_type="rest"),
        ]
    )

    assert result.tick_no == 1
    assert len(result.accepted) == 2
    assert len(result.rejected) == 0
    assert world.current_time.isoformat() == "2026-03-07T08:05:00"


def test_world_time_context_exposes_calendar_fields():
    world = build_world()

    clock = world.time_context()

    assert clock["hour"] == 8
    assert clock["minute"] == 0
    assert clock["weekday_name"] == "Saturday"
    assert clock["is_weekend"] is True
    assert clock["time_period"] == "morning"
