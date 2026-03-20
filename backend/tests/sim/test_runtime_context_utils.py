from datetime import datetime

from app.scenario.truman_world.types import build_director_guidance
from app.scenario.truman_world.rules import RuntimeRoleSemantics
from app.sim.runtime_context_utils import (
    build_agent_world_context,
    extract_subject_alert_from_agent_data,
    extract_truman_suspicion_from_agent_data,
)
from app.sim.types import AgentDecisionSnapshot
from app.sim.world import AgentState, LocationState, WorldState


def _build_world() -> WorldState:
    return WorldState(
        current_time=datetime(2026, 1, 5, 9, 30),
        tick_minutes=5,
        locations={
            "home": LocationState(id="home", name="Home", location_type="home"),
            "cafe": LocationState(
                id="cafe",
                name="Cafe",
                location_type="cafe",
                occupants={"alice", "bob"},
            ),
        },
        agents={
            "alice": AgentState(
                id="alice",
                name="Alice",
                location_id="cafe",
                occupation="barista",
                status={"mood": "calm"},
            ),
            "bob": AgentState(
                id="bob",
                name="Bob",
                location_id="cafe",
                occupation="friend",
                status={"mood": "busy"},
            ),
            "truman": AgentState(
                id="truman",
                name="Truman",
                location_id="home",
                status={"suspicion_score": 0.75},
            ),
        },
    )


def test_build_agent_world_context_includes_location_occupants_and_guidance():
    world = _build_world()
    world.world_effects = {
        "power_outages": [
            {
                "location_id": "cafe",
                "start_tick": 0,
                "end_tick": 3,
                "message": "Cafe blackout",
            }
        ]
    }

    context = build_agent_world_context(
        world=world,
        current_goal="talk",
        current_location_id="cafe",
        home_location_id="home",
        nearby_agent_id="bob",
        current_status={"energy": 0.8},
        subject_alert_score=0.25,
        world_role="cast",
        director_guidance=build_director_guidance(
            scene_goal="soft_check_in",
            priority=None,
            message_hint="keep it casual",
            target_agent_id="truman",
            location_hint="cafe",
            reason="watch suspicion",
        ),
        workplace_location_id="cafe",
    )

    assert context["current_location_name"] == "Cafe"
    assert context["current_location_type"] == "cafe"
    assert {occupant["id"] for occupant in context["location_occupants"]} == {"alice", "bob"}
    assert any(occupant["name"] == "Alice" for occupant in context["location_occupants"])
    assert context["nearby_agent"]["name"] == "Bob"
    assert context["director_scene_goal"] == "soft_check_in"
    assert context["director_priority"] == "advisory"
    assert context["director_message_hint"] == "keep it casual"
    assert context["subject_alert_score"] == 0.25
    assert "truman_suspicion_score" not in context
    assert context["workplace_location_id"] == "cafe"
    assert context["active_world_effects"] == ["power_outage"]
    assert context["current_location_power_status"] == "off"
    assert context["current_location_effects"][0]["effect_type"] == "power_outage"


def test_build_agent_world_context_omits_subject_alert_score_when_disabled():
    world = _build_world()

    context = build_agent_world_context(
        world=world,
        current_goal="rest",
        current_location_id="home",
        home_location_id="home",
        nearby_agent_id=None,
        current_status={"energy": 0.8},
        subject_alert_score=None,
        world_role="protagonist",
    )

    assert "subject_alert_score" not in context


def test_extract_truman_suspicion_from_agent_data_returns_first_truman_score():
    world = _build_world()
    agent_data = [
        AgentDecisionSnapshot(
            id="alice",
            profile={"world_role": "cast"},
            current_goal="work",
            home_location_id="home",
            current_location_id="cafe",
            recent_events=[],
        ),
        AgentDecisionSnapshot(
            id="truman",
            profile={"world_role": "truman"},
            current_goal="rest",
            home_location_id="home",
            current_location_id="home",
            recent_events=[],
        ),
    ]

    suspicion = extract_truman_suspicion_from_agent_data(agent_data, world)
    alert_score = extract_subject_alert_from_agent_data(agent_data, world)

    assert suspicion == 0.75
    assert alert_score == suspicion


def test_extract_truman_suspicion_from_agent_data_returns_zero_without_matching_state():
    world = _build_world()
    agent_data = [
        AgentDecisionSnapshot(
            id="ghost-truman",
            profile={"world_role": "truman"},
            current_goal="rest",
            home_location_id="home",
            current_location_id="home",
            recent_events=[],
        )
    ]

    suspicion = extract_truman_suspicion_from_agent_data(agent_data, world)

    assert suspicion == 0.0


def test_extract_subject_alert_from_agent_data_supports_runtime_semantics():
    world = WorldState(
        current_time=datetime(2026, 1, 5, 9, 30),
        tick_minutes=5,
        locations={},
        agents={
            "hero": AgentState(
                id="hero",
                name="Hero",
                location_id="home",
                status={"anomaly_score": 0.55},
            )
        },
    )
    agent_data = [
        AgentDecisionSnapshot(
            id="hero",
            profile={"world_role": "protagonist"},
            current_goal="rest",
            home_location_id="home",
            current_location_id="home",
            recent_events=[],
        )
    ]

    alert_score = extract_subject_alert_from_agent_data(
        agent_data,
        world,
        semantics=RuntimeRoleSemantics(
            subject_role="protagonist",
            support_roles=["ally"],
            alert_metric="anomaly_score",
        ),
    )

    assert alert_score == 0.55
