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


def _build_collocated_world() -> WorldState:
    """Two agents Alice and Bob already at the same location (park)."""
    park = LocationState(id="park", name="Park", capacity=4, occupants={"alice", "bob"})
    agents = {
        "alice": AgentState(id="alice", name="Alice", location_id="park", status={}),
        "bob": AgentState(id="bob", name="Bob", location_id="park", status={}),
    }
    return WorldState(
        current_time=datetime(2026, 3, 7, 8, 0, 0),
        tick_minutes=5,
        locations={"park": park},
        agents=agents,
    )


def test_action_resolver_only_one_talk_per_pair_per_tick():
    """When both agents try to talk to each other in the same tick, only the
    first intent is accepted; the second is rejected with reason
    'conversation_turn_taken'."""
    world = _build_collocated_world()
    resolver = ActionResolver()
    resolver.reset_tick()

    result_alice = resolver.resolve(
        world,
        ActionIntent(
            agent_id="alice",
            action_type="talk",
            target_agent_id="bob",
            payload={"message": "Hi Bob!"},
        ),
    )
    result_bob = resolver.resolve(
        world,
        ActionIntent(
            agent_id="bob",
            action_type="talk",
            target_agent_id="alice",
            payload={"message": "Hi Alice!"},
        ),
    )

    assert result_alice.accepted is True
    assert result_bob.accepted is False
    assert result_bob.reason == "conversation_turn_taken"


def test_action_resolver_resets_talked_agents_between_ticks():
    """After reset_tick(), the same pair can talk again in the next tick."""
    world = _build_collocated_world()
    resolver = ActionResolver()

    # Tick 1: Alice speaks
    resolver.reset_tick()
    r1 = resolver.resolve(
        world,
        ActionIntent(
            agent_id="alice",
            action_type="talk",
            target_agent_id="bob",
            payload={"message": "Hello!"},
        ),
    )
    assert r1.accepted is True

    # Tick 2: Bob should now be allowed to speak (new tick)
    resolver.reset_tick()
    r2 = resolver.resolve(
        world,
        ActionIntent(
            agent_id="bob",
            action_type="talk",
            target_agent_id="alice",
            payload={"message": "Hey there!"},
        ),
    )
    assert r2.accepted is True


def test_simulation_runner_resets_talked_agents_each_tick():
    """SimulationRunner.tick() must call reset_tick() so consecutive ticks
    each allow exactly one talk per pair."""
    world = _build_collocated_world()
    runner = SimulationRunner(world)

    # Tick 1: both try to talk – only first accepted
    result1 = runner.tick(
        [
            ActionIntent(
                agent_id="alice",
                action_type="talk",
                target_agent_id="bob",
                payload={"message": "Tick 1 Alice"},
            ),
            ActionIntent(
                agent_id="bob",
                action_type="talk",
                target_agent_id="alice",
                payload={"message": "Tick 1 Bob"},
            ),
        ]
    )
    assert len(result1.accepted) == 1
    assert len(result1.rejected) == 1
    assert result1.rejected[0].reason == "conversation_turn_taken"

    # Tick 2: both try again – only first accepted (reset happened)
    result2 = runner.tick(
        [
            ActionIntent(
                agent_id="alice",
                action_type="talk",
                target_agent_id="bob",
                payload={"message": "Tick 2 Alice"},
            ),
            ActionIntent(
                agent_id="bob",
                action_type="talk",
                target_agent_id="alice",
                payload={"message": "Tick 2 Bob"},
            ),
        ]
    )
    assert len(result2.accepted) == 1
    assert len(result2.rejected) == 1
