from app.director.observer import DirectorObserver, DirectorObserverSemantics
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

    assert assessment.subject_agent_id == "truman-1"
    assert assessment.subject_alert_score == 0.68
    assert assessment.active_support_count == 1
    assert assessment.active_cast_count == assessment.active_support_count
    assert assessment.suspicion_level == "alerted"
    assert assessment.continuity_risk in {"watch", "elevated", "critical"}
    assert assessment.focus_agent_ids[0] == "truman-1"
    assert assessment.notes


def test_director_observer_uses_semantics_for_subject_support_and_alert_metric():
    observer = DirectorObserver(
        DirectorObserverSemantics(
            subject_role="protagonist",
            support_roles=["ally", "cast"],
            alert_metric="anomaly_score",
        )
    )
    agents = [
        Agent(
            id="hero-1",
            run_id="run-2",
            name="Hero",
            occupation="resident",
            profile={"world_role": "protagonist"},
            status={"anomaly_score": 0.74},
            personality={},
            current_plan={},
        ),
        Agent(
            id="ally-1",
            run_id="run-2",
            name="Ally",
            occupation="friend",
            profile={"world_role": "ally"},
            status={},
            personality={},
            current_plan={},
        ),
        Agent(
            id="cast-1",
            run_id="run-2",
            name="Cast",
            occupation="neighbor",
            profile={"world_role": "cast"},
            status={},
            personality={},
            current_plan={},
        ),
    ]
    events = [
        Event(
            id="evt-10",
            run_id="run-2",
            tick_no=2,
            event_type="move_rejected",
            actor_agent_id="hero-1",
            payload={"agent_id": "hero-1"},
        )
    ]

    assessment = observer.assess(
        run_id="run-2",
        current_tick=2,
        agents=agents,
        events=events,
        previous_suspicion_score=0.42,
    )

    assert assessment.subject_agent_id == "hero-1"
    assert assessment.subject_alert_score == 0.74
    assert assessment.active_support_count == 2
    assert assessment.suspicion_level == "alerted"
    assert assessment.focus_agent_ids[0] == "hero-1"
    assert any("主体告警值" in note for note in assessment.notes)


def test_director_observer_skips_alert_tracking_when_disabled():
    observer = DirectorObserver(
        DirectorObserverSemantics(
            subject_role="protagonist",
            support_roles=["ally"],
            alert_metric="anomaly_score",
            subject_alert_tracking=False,
        )
    )
    agents = [
        Agent(
            id="hero-1",
            run_id="run-3",
            name="Hero",
            occupation="resident",
            profile={"world_role": "protagonist"},
            status={"anomaly_score": 0.74},
            personality={},
            current_plan={},
        ),
        Agent(
            id="ally-1",
            run_id="run-3",
            name="Ally",
            occupation="friend",
            profile={"world_role": "ally"},
            status={},
            personality={},
            current_plan={},
        ),
    ]
    events = [
        Event(
            id="evt-20",
            run_id="run-3",
            tick_no=2,
            event_type="move_rejected",
            actor_agent_id="hero-1",
            payload={"agent_id": "hero-1"},
        )
    ]

    assessment = observer.assess(
        run_id="run-3",
        current_tick=2,
        agents=agents,
        events=events,
        previous_suspicion_score=0.42,
    )

    assert assessment.subject_agent_id == "hero-1"
    assert assessment.subject_alert_score == 0.0
    assert assessment.suspicion_level == "low"
    assert assessment.suspicion_trend is None
    assert assessment.continuity_risk in {"watch", "elevated", "critical"}
    assert all("主体告警值" not in note for note in assessment.notes)
