from app.sim.event_utils import build_event, format_event_for_context
from app.store.models import Event


class _AgentState:
    def __init__(self, name: str) -> None:
        self.name = name


class _LocationState:
    def __init__(self, name: str) -> None:
        self.name = name


def test_build_event_sets_public_visibility_for_accepted_actions():
    event = build_event(
        run_id="run-1",
        tick_no=3,
        world_time="2026-01-01T09:00:00",
        action_type="move",
        payload={"agent_id": "alice", "to_location_id": "loc-park"},
        accepted=True,
    )

    assert event.run_id == "run-1"
    assert event.event_type == "move"
    assert event.actor_agent_id == "alice"
    assert event.location_id == "loc-park"
    assert event.visibility == "public"


def test_build_event_maps_accepted_talk_to_speech_event():
    event = build_event(
        run_id="run-1",
        tick_no=3,
        world_time="2026-01-01T09:00:00",
        action_type="talk",
        payload={
            "agent_id": "alice",
            "target_agent_id": "bob",
            "location_id": "cafe",
            "message": "hello",
            "conversation_event_type": "speech",
            "speaker_agent_id": "alice",
        },
        accepted=True,
    )

    assert event.event_type == "speech"
    assert event.actor_agent_id == "alice"
    assert event.target_agent_id == "bob"


def test_build_event_supports_listen_action():
    event = build_event(
        run_id="run-1",
        tick_no=3,
        world_time="2026-01-01T09:00:00",
        action_type="listen",
        payload={
            "agent_id": "bob",
            "target_agent_id": "alice",
            "location_id": "cafe",
            "conversation_id": "conv-1",
            "conversation_role": "listener",
            "conversation_event_type": "listen",
            "speaker_agent_id": "alice",
        },
        accepted=True,
    )

    assert event.event_type == "listen"
    assert event.actor_agent_id == "bob"
    assert event.target_agent_id == "alice"
    assert event.payload["conversation_role"] == "listener"
    assert event.payload["conversation_event_type"] == "listen"
    assert event.payload["speaker_agent_id"] == "alice"


def test_build_event_supports_conversation_started_action():
    event = build_event(
        run_id="run-1",
        tick_no=3,
        world_time="2026-01-01T09:00:00",
        action_type="conversation_started",
        payload={
            "agent_id": "alice",
            "target_agent_id": "bob",
            "location_id": "cafe",
            "conversation_id": "conv-1",
            "conversation_event_type": "conversation_started",
            "participant_ids": ["alice", "bob"],
        },
        accepted=True,
    )

    assert event.event_type == "conversation_started"
    assert event.actor_agent_id == "alice"
    assert event.target_agent_id == "bob"
    assert event.payload["conversation_event_type"] == "conversation_started"


def test_build_event_sets_rejected_type_and_system_visibility():
    event = build_event(
        run_id="run-1",
        tick_no=4,
        world_time="2026-01-01T09:05:00",
        action_type="talk",
        payload={"agent_id": "alice", "target_agent_id": "bob", "location_id": "cafe"},
        accepted=False,
    )

    assert event.event_type == "talk_rejected"
    assert event.target_agent_id == "bob"
    assert event.location_id == "cafe"
    assert event.visibility == "system"


def test_build_event_keeps_invalid_requested_target_only_in_payload():
    event = build_event(
        run_id="run-1",
        tick_no=4,
        world_time="2026-01-01T09:05:00",
        action_type="talk",
        payload={
            "agent_id": "alice",
            "target_agent_id": None,
            "requested_target_agent_id": "marlon",
            "location_id": "cafe",
        },
        accepted=False,
    )

    assert event.event_type == "talk_rejected"
    assert event.target_agent_id is None
    assert event.payload["requested_target_agent_id"] == "marlon"


def test_format_event_for_context_uses_names_and_defaults():
    event = Event(
        id="event-1",
        run_id="run-1",
        tick_no=7,
        event_type="speech",
        actor_agent_id="alice",
        target_agent_id="bob",
        location_id="cafe",
        payload={
            "message": "hello",
            "conversation_id": "conv-1",
            "conversation_role": "speaker",
            "conversation_event_type": "speech",
            "speaker_agent_id": "alice",
            "participant_ids": ["alice", "bob", "carol"],
        },
    )

    formatted = format_event_for_context(
        event,
        agent_states={"alice": _AgentState("Alice"), "bob": _AgentState("Bob")},
        location_states={"cafe": _LocationState("Cafe")},
    )

    assert formatted == {
        "event_type": "speech",
        "tick_no": 7,
        "actor_name": "Alice",
        "target_name": "Bob",
        "location_name": "Cafe",
        "message": "hello",
        "conversation_id": "conv-1",
        "conversation_role": "speaker",
        "conversation_event_type": "speech",
        "speaker_agent_id": "alice",
        "speaker_name": "Alice",
        "participant_ids": ["alice", "bob", "carol"],
    }


def test_format_event_for_context_falls_back_for_unknown_actor():
    event = Event(
        id="event-2",
        run_id="run-1",
        tick_no=8,
        event_type="move",
        actor_agent_id="missing",
        payload={},
    )

    formatted = format_event_for_context(event, agent_states={}, location_states={})

    assert formatted["actor_name"] == "某人"
    assert "target_name" not in formatted
    assert "location_name" not in formatted


def test_prompt_loader_formats_conversation_structure_events():
    from app.agent.prompt_loader import PromptLoader

    loader = PromptLoader()

    started = loader._format_event(
        {
            "event_type": "conversation_started",
            "tick_no": 3,
            "actor_name": "Alice",
            "target_name": "Bob",
        }
    )
    joined = loader._format_event(
        {
            "event_type": "conversation_joined",
            "tick_no": 4,
            "actor_name": "Carol",
            "target_name": "Alice",
        }
    )

    assert started == "[Tick 3] Alice 与 Bob 开始了一段对话"
    assert joined == "[Tick 4] Carol 加入了 Alice 主导的对话"
