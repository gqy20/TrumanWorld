from datetime import datetime

from app.sim.action_resolver import ActionIntent, ActionResolver
from app.sim.conversation_scheduler import ConversationScheduler
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


def test_action_resolver_normalizes_talk_target_from_agent_name():
    world = _build_collocated_world()
    world.agents["bob"].name = "Marlon"
    resolver = ActionResolver()

    result = resolver.resolve(
        world,
        ActionIntent(
            agent_id="alice",
            action_type="talk",
            target_agent_id="marlon",
            payload={"message": "Hi Marlon."},
        ),
    )

    assert result.accepted is True
    assert result.event_payload["target_agent_id"] == "bob"


def test_action_resolver_rejects_unknown_talk_target_without_invalid_target_agent_id():
    world = _build_collocated_world()
    resolver = ActionResolver()

    result = resolver.resolve(
        world,
        ActionIntent(
            agent_id="alice",
            action_type="talk",
            target_agent_id="marlon",
            payload={"message": "Hi Marlon."},
        ),
    )

    assert result.accepted is False
    assert result.reason == "target_not_found"
    assert result.event_payload["target_agent_id"] is None
    assert result.event_payload["requested_target_agent_id"] == "marlon"


def test_action_resolver_downgrades_work_without_valid_work_context():
    world = build_world()
    resolver = ActionResolver()

    result = resolver.resolve(
        world,
        ActionIntent(agent_id="alice", action_type="work"),
    )

    assert result.accepted is True
    assert result.action_type == "rest"
    assert result.reason == "downgraded_invalid_work_context"
    assert result.event_payload["location_id"] == "home"


def test_action_resolver_allows_work_at_known_workplace():
    world = build_world()
    world.agents["bob"].workplace_id = "cafe"
    resolver = ActionResolver()

    result = resolver.resolve(
        world,
        ActionIntent(agent_id="bob", action_type="work"),
    )

    assert result.accepted is True
    assert result.action_type == "work"
    assert result.reason == "accepted"
    assert result.event_payload["location_id"] == "cafe"


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
    assert result.tick_delta == 1
    assert world.current_time.isoformat() == "2026-03-07T08:05:00"


def test_simulation_runner_skips_sleep_hours_in_single_tick():
    world = WorldState(
        current_time=datetime(2026, 3, 7, 22, 55, 0),
        current_tick=203,
        tick_minutes=5,
        locations={"home": LocationState(id="home", name="Home", capacity=2, occupants={"alice"})},
        agents={"alice": AgentState(id="alice", name="Alice", location_id="home", status={})},
    )
    runner = SimulationRunner(world)
    runner.tick_no = 203

    result = runner.tick([ActionIntent(agent_id="alice", action_type="rest")])

    assert result.tick_delta == 85
    assert result.tick_no == 288
    assert result.world_time == "2026-03-08T06:00:00"
    assert world.current_tick == 288
    assert world.current_time.isoformat() == "2026-03-08T06:00:00"


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


def test_action_resolver_suppresses_rest_for_talk_target():
    """When Alice talks to Bob, Bob's rest intent in the same tick should be
    suppressed (rejected with 'agent_in_conversation') so no spurious rest
    event appears alongside the talk event."""
    world = _build_collocated_world()
    resolver = ActionResolver()
    scheduler = ConversationScheduler()
    resolver.reset_tick()

    intents = [
        ActionIntent(
            agent_id="alice",
            action_type="talk",
            target_agent_id="bob",
            payload={"message": "Hey Bob!"},
        ),
        ActionIntent(agent_id="bob", action_type="rest"),
    ]
    sessions, assignments = scheduler.schedule(intents, world)
    resolver.prefill_conversation_assignments(
        {
            assignment.agent_id: {
                "role": assignment.role,
                "conversation_id": assignment.conversation_id,
                "participant_ids": next(
                    (
                        list(session.participant_ids)
                        for session in sessions
                        if session.id == assignment.conversation_id
                    ),
                    [],
                ),
            }
            for assignment in assignments.values()
        }
    )

    result_alice = resolver.resolve(world, intents[0])
    result_bob_rest = resolver.resolve(world, intents[1])

    assert result_alice.accepted is True
    assert result_bob_rest.accepted is False
    assert result_bob_rest.reason == "agent_in_conversation"


def test_simulation_runner_uses_conversation_scheduler_to_reserve_listener():
    world = _build_collocated_world()
    scheduler = ConversationScheduler()
    runner = SimulationRunner(world)

    intents = [
        ActionIntent(
            agent_id="alice",
            action_type="talk",
            target_agent_id="bob",
            payload={"message": "Hey Bob!"},
        ),
        ActionIntent(agent_id="bob", action_type="work"),
    ]

    sessions, assignments = scheduler.schedule(intents, world)
    result = runner.tick(intents)

    assert len(sessions) == 1
    assert assignments["bob"].role == "listener"
    assert [item.action_type for item in result.accepted] == [
        "conversation_started",
        "talk",
        "listen",
    ]
    assert result.rejected[0].reason == "agent_in_conversation"


def test_simulation_runner_allows_joiner_to_enter_session_without_taking_turn():
    world = WorldState(
        current_time=datetime(2026, 3, 7, 8, 0, 0),
        tick_minutes=5,
        locations={
            "plaza": LocationState(
                id="plaza",
                name="Plaza",
                capacity=4,
                occupants={"alice", "bob", "carol"},
            )
        },
        agents={
            "alice": AgentState(id="alice", name="Alice", location_id="plaza", status={}),
            "bob": AgentState(id="bob", name="Bob", location_id="plaza", status={}),
            "carol": AgentState(id="carol", name="Carol", location_id="plaza", status={}),
        },
    )
    runner = SimulationRunner(world)

    result = runner.tick(
        [
            ActionIntent(
                agent_id="alice",
                action_type="talk",
                target_agent_id="bob",
                payload={"message": "Hey Bob!"},
            ),
            ActionIntent(
                agent_id="carol",
                action_type="talk",
                target_agent_id="bob",
                payload={"message": "Mind if I join?"},
            ),
        ]
    )

    assert len(result.accepted) == 5
    assert len(result.rejected) == 0
    started_events = [
        item for item in result.accepted if item.action_type == "conversation_started"
    ]
    joined_events = [item for item in result.accepted if item.action_type == "conversation_joined"]
    accepted_talk = next(item for item in result.accepted if item.action_type == "talk")
    accepted_listens = [item for item in result.accepted if item.action_type == "listen"]

    assert len(started_events) == 1
    assert len(joined_events) == 1
    assert len(accepted_listens) == 2
    assert started_events[0].event_payload["conversation_event_type"] == "conversation_started"
    assert joined_events[0].event_payload["conversation_event_type"] == "conversation_joined"
    assert "conversation_id" in accepted_talk.event_payload
    assert accepted_talk.event_payload["conversation_role"] == "speaker"
    assert accepted_talk.event_payload["conversation_event_type"] == "speech"
    assert accepted_talk.event_payload["speaker_agent_id"] == "alice"
    assert all(item.event_payload["conversation_role"] == "listener" for item in accepted_listens)
    assert all(
        item.event_payload["conversation_event_type"] == "listen" for item in accepted_listens
    )
    assert all(item.event_payload["speaker_agent_id"] == "alice" for item in accepted_listens)


def test_simulation_runner_tags_listener_suppression_with_conversation_id():
    world = WorldState(
        current_time=datetime(2026, 3, 7, 8, 0, 0),
        tick_minutes=5,
        locations={
            "plaza": LocationState(
                id="plaza",
                name="Plaza",
                capacity=4,
                occupants={"alice", "bob", "carol"},
            )
        },
        agents={
            "alice": AgentState(id="alice", name="Alice", location_id="plaza", status={}),
            "bob": AgentState(id="bob", name="Bob", location_id="plaza", status={}),
            "carol": AgentState(id="carol", name="Carol", location_id="plaza", status={}),
        },
    )
    runner = SimulationRunner(world)

    result = runner.tick(
        [
            ActionIntent(
                agent_id="alice",
                action_type="talk",
                target_agent_id="bob",
                payload={"message": "Hey Bob!"},
            ),
            ActionIntent(agent_id="carol", action_type="talk", target_agent_id="bob"),
            ActionIntent(agent_id="bob", action_type="work"),
        ]
    )

    started_events = [
        item for item in result.accepted if item.action_type == "conversation_started"
    ]
    joined_events = [item for item in result.accepted if item.action_type == "conversation_joined"]
    accepted_talk = next(item for item in result.accepted if item.action_type == "talk")
    accepted_listens = [item for item in result.accepted if item.action_type == "listen"]
    suppressed_work = next(item for item in result.rejected if item.action_type == "work")

    assert len(started_events) == 1
    assert len(joined_events) == 1
    assert len(accepted_listens) == 2
    assert suppressed_work.reason == "agent_in_conversation"
    assert (
        suppressed_work.event_payload["conversation_id"]
        == accepted_talk.event_payload["conversation_id"]
    )
    assert suppressed_work.event_payload["conversation_role"] == "listener"
    assert accepted_talk.event_payload["conversation_role"] == "speaker"
    assert accepted_talk.event_payload["conversation_event_type"] == "speech"
    assert all(item.event_payload["conversation_role"] == "listener" for item in accepted_listens)
    assert all(
        item.event_payload["conversation_event_type"] == "listen" for item in accepted_listens
    )


def test_action_resolver_suppresses_work_for_talk_target_regardless_of_order():
    """Even when the target's work intent is processed BEFORE the talk intent,
    scheduler assignments ensure the work is still suppressed."""
    world = _build_collocated_world()
    runner = SimulationRunner(world)

    # Bob's work comes first in the list, Alice's talk comes second
    result = runner.tick(
        [
            ActionIntent(agent_id="bob", action_type="work"),
            ActionIntent(
                agent_id="alice",
                action_type="talk",
                target_agent_id="bob",
                payload={"message": "Hey Bob!"},
            ),
        ]
    )

    accepted_types = {r.action_type for r in result.accepted}
    rejected_reasons = {r.reason for r in result.rejected}

    assert "talk" in accepted_types
    assert "work" not in accepted_types
    assert "agent_in_conversation" in rejected_reasons


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
    assert len(result1.accepted) == 3
    assert len(result1.rejected) == 1
    assert {item.action_type for item in result1.accepted} == {
        "conversation_started",
        "talk",
        "listen",
    }
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
    assert len(result2.accepted) == 3
    assert len(result2.rejected) == 1
    assert {item.action_type for item in result2.accepted} == {
        "conversation_started",
        "talk",
        "listen",
    }
