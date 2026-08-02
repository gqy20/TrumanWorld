from __future__ import annotations

from app.director.candidates import build_actor_candidates, rank_eligible_candidates
from app.store.models import Agent, Event


def _agent(agent_id: str, name: str, *, location: str, movement: dict | None = None) -> Agent:
    return Agent(
        id=agent_id,
        run_id="run-1",
        name=name,
        current_location_id=location,
        current_goal="rest",
        movement=movement or {},
        profile={"world_role": "cast" if agent_id != "subject" else "truman"},
        personality={},
        status={},
        current_plan={},
    )


def test_actor_candidates_exclude_moving_and_unrelated_conversation() -> None:
    agents = [
        _agent("subject", "Truman", location="home"),
        _agent("busy", "Marlon", location="home"),
        _agent("moving", "Meryl", location="office", movement={"to": "home"}),
        _agent("ready", "Lauren", location="home"),
    ]
    event = Event(
        id="event-1",
        run_id="run-1",
        tick_no=9,
        event_type="speech",
        actor_agent_id="busy",
        target_agent_id="other",
        payload={"conversation_id": "c-1", "participant_ids": ["busy", "other"]},
    )

    candidates = build_actor_candidates(
        agents=agents,
        events=[event],
        current_tick=10,
        subject_agent_id="subject",
    )

    assert candidates["busy"].availability == "in_conversation"
    assert candidates["busy"].eligible is False
    assert candidates["moving"].availability == "moving"
    assert candidates["moving"].eligible is False
    assert [item.agent_id for item in rank_eligible_candidates(candidates)] == [
        "ready",
        "subject",
    ]


def test_actor_in_conversation_with_subject_remains_eligible_and_ranks_first() -> None:
    agents = [
        _agent("subject", "Truman", location="home"),
        _agent("engaged", "Meryl", location="home"),
        _agent("ready", "Lauren", location="home"),
    ]
    event = Event(
        id="event-1",
        run_id="run-1",
        tick_no=5,
        event_type="speech",
        actor_agent_id="engaged",
        target_agent_id="subject",
        payload={"conversation_id": "c-1", "participant_ids": ["engaged", "subject"]},
    )

    candidates = build_actor_candidates(
        agents=agents,
        events=[event],
        current_tick=5,
        subject_agent_id="subject",
    )

    assert candidates["engaged"].availability == "engaged_with_subject"
    assert candidates["engaged"].eligible is True
    assert rank_eligible_candidates(candidates)[0].agent_id == "engaged"


def test_closed_conversation_releases_actor_candidate() -> None:
    agents = [
        _agent("subject", "Truman", location="home"),
        _agent("actor", "Marlon", location="home"),
    ]
    events = [
        Event(
            id="event-speech",
            run_id="run-1",
            tick_no=9,
            event_type="speech",
            payload={"conversation_id": "c-1", "participant_ids": ["actor", "other"]},
        ),
        Event(
            id="event-close",
            run_id="run-1",
            tick_no=10,
            event_type="conversation_closed",
            payload={"conversation_id": "c-1", "participant_ids": ["actor", "other"]},
        ),
    ]

    candidates = build_actor_candidates(
        agents=agents,
        events=events,
        current_tick=10,
        subject_agent_id="subject",
    )

    assert candidates["actor"].availability == "available"
    assert candidates["actor"].eligible is True
