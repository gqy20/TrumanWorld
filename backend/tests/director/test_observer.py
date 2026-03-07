from app.director.observer import DirectorObserver
from app.store.models import Agent, Event


def test_director_observer_assesses_truman_world_state():
    observer = DirectorObserver()
    agents = [
        Agent(
            id="truman-1",
            run_id="run-1",
            name="Truman",
            occupation="resident",
            profile={"world_role": "truman"},
            status={"suspicion_score": 0.68},
            personality={},
            current_plan={},
        ),
        Agent(
            id="friend-1",
            run_id="run-1",
            name="Marlon",
            occupation="friend",
            profile={"world_role": "cast"},
            status={},
            personality={},
            current_plan={},
        ),
    ]
    events = [
        Event(
            id="evt-1",
            run_id="run-1",
            tick_no=3,
            event_type="move_rejected",
            actor_agent_id="truman-1",
            payload={"agent_id": "truman-1"},
        ),
        Event(
            id="evt-2",
            run_id="run-1",
            tick_no=3,
            event_type="talk",
            actor_agent_id="friend-1",
            target_agent_id="truman-1",
            payload={"agent_id": "friend-1", "target_agent_id": "truman-1"},
        ),
    ]

    assessment = observer.assess(
        run_id="run-1",
        current_tick=3,
        agents=agents,
        events=events,
    )

    assert assessment.truman_agent_id == "truman-1"
    assert assessment.truman_suspicion_score == 0.68
    assert assessment.suspicion_level == "alerted"
    assert assessment.continuity_risk in {"watch", "elevated", "critical"}
    assert assessment.focus_agent_ids[0] == "truman-1"
    assert assessment.notes
