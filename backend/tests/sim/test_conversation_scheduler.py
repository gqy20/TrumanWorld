from datetime import datetime

from app.sim.action_resolver import ActionIntent
from app.sim.conversation_scheduler import ConversationScheduler
from app.sim.world import ActiveConversationState, AgentState, LocationState, WorldState


def _build_collocated_world() -> WorldState:
    plaza = LocationState(id="plaza", name="Plaza", capacity=6, occupants={"alice", "bob", "carol"})
    agents = {
        "alice": AgentState(id="alice", name="Alice", location_id="plaza", status={}),
        "bob": AgentState(id="bob", name="Bob", location_id="plaza", status={}),
        "carol": AgentState(id="carol", name="Carol", location_id="plaza", status={}),
    }
    return WorldState(
        current_time=datetime(2026, 3, 7, 8, 0, 0),
        tick_minutes=5,
        locations={"plaza": plaza},
        agents=agents,
    )


def test_conversation_scheduler_creates_session_for_valid_talk_intent():
    world = _build_collocated_world()
    scheduler = ConversationScheduler()

    sessions, assignments = scheduler.schedule(
        [
            ActionIntent(agent_id="alice", action_type="talk", target_agent_id="bob"),
            ActionIntent(agent_id="carol", action_type="rest"),
        ],
        world,
    )

    assert len(sessions) == 1
    assert sessions[0].participant_ids == ["alice", "bob"]
    assert sessions[0].active_speaker_id == "alice"
    assert assignments["alice"].role == "speaker"
    assert assignments["bob"].role == "listener"
    assert assignments["bob"].conversation_id == sessions[0].id


def test_conversation_scheduler_converts_second_talk_into_join_for_busy_target():
    world = _build_collocated_world()
    scheduler = ConversationScheduler()

    sessions, assignments = scheduler.schedule(
        [
            ActionIntent(agent_id="alice", action_type="talk", target_agent_id="bob"),
            ActionIntent(agent_id="carol", action_type="talk", target_agent_id="bob"),
        ],
        world,
    )

    assert len(sessions) == 1
    assert assignments["alice"].role == "speaker"
    assert assignments["bob"].role == "listener"
    assert assignments["carol"].role == "listener"
    assert assignments["carol"].reason == "conversation_joiner"


def test_conversation_scheduler_adds_joiner_to_existing_session():
    world = _build_collocated_world()
    scheduler = ConversationScheduler()

    sessions, assignments = scheduler.schedule(
        [
            ActionIntent(agent_id="alice", action_type="talk", target_agent_id="bob"),
            ActionIntent(agent_id="carol", action_type="talk", target_agent_id="bob"),
        ],
        world,
    )

    assert len(sessions) == 1
    assert sessions[0].participant_ids == ["alice", "bob", "carol"]
    assert sessions[0].active_speaker_id == "alice"
    assert assignments["alice"].role == "speaker"
    assert assignments["bob"].role == "listener"
    assert assignments["carol"].role == "listener"
    assert assignments["carol"].reason == "conversation_joiner"
    assert assignments["carol"].conversation_id == sessions[0].id


def test_conversation_scheduler_prioritizes_pending_reply_and_skips_reciprocal_rejection():
    world = _build_collocated_world()
    scheduler = ConversationScheduler()

    sessions, assignments = scheduler.schedule(
        [
            ActionIntent(agent_id="alice", action_type="talk", target_agent_id="bob"),
            ActionIntent(
                agent_id="bob",
                action_type="talk",
                target_agent_id="alice",
                payload={"intent_source": "pending_reply_bias"},
            ),
        ],
        world,
    )

    assert len(sessions) == 1
    assert sessions[0].active_speaker_id == "bob"
    assert assignments["bob"].role == "speaker"
    assert assignments["alice"].role == "listener"
    assert assignments["alice"].reason == "reciprocal_talk_listener"


def test_conversation_scheduler_refreshes_existing_session_location_on_continuation():
    world = _build_collocated_world()
    world.current_tick = 6
    world.active_conversations = {
        "conv-1": ActiveConversationState(
            id="conv-1",
            location_id="dorm",
            participant_ids=["alice", "bob"],
            active_speaker_id="alice",
            last_tick_no=5,
        )
    }

    scheduler = ConversationScheduler()
    sessions, assignments = scheduler.schedule(
        [
            ActionIntent(agent_id="alice", action_type="talk", target_agent_id="bob"),
        ],
        world,
    )

    assert len(sessions) == 1
    assert sessions[0].id == "conv-1"
    assert sessions[0].location_id == "plaza"
    assert assignments["alice"].conversation_id == "conv-1"


def test_conversation_scheduler_closes_session_when_no_one_continues_talking():
    world = _build_collocated_world()
    world.current_tick = 6
    world.active_conversations = {
        "conv-1": ActiveConversationState(
            id="conv-1",
            location_id="plaza",
            participant_ids=["alice", "bob"],
            active_speaker_id="alice",
            last_tick_no=5,
            started_tick_no=1,
            turn_count=4,
        )
    }

    sessions, assignments = ConversationScheduler().schedule(
        [ActionIntent(agent_id="alice", action_type="move", target_location_id="elsewhere")],
        world,
    )

    assert sessions == []
    assert assignments == {}


def test_conversation_scheduler_does_not_reopen_session_at_turn_limit():
    world = _build_collocated_world()
    world.current_tick = 6
    world.active_conversations = {
        "conv-1": ActiveConversationState(
            id="conv-1",
            location_id="plaza",
            participant_ids=["alice", "bob"],
            active_speaker_id="alice",
            last_tick_no=5,
            started_tick_no=1,
            turn_count=6,
            phase="closing",
        )
    }

    sessions, _assignments = ConversationScheduler().schedule([], world)

    assert sessions == []
