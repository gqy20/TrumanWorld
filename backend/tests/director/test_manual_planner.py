from app.director.manual_planner import ManualDirectorPlanner
from app.protocol.simulation import (
    DIRECTOR_SCENE_ACTIVITY,
    DIRECTOR_SCENE_GATHER,
    DIRECTOR_SCENE_POWER_OUTAGE,
    DIRECTOR_SCENE_SHUTDOWN,
    DIRECTOR_SCENE_WEATHER_CHANGE,
)
from app.store.models import Agent


def _make_agent(agent_id: str, world_role: str) -> Agent:
    return Agent(
        id=agent_id,
        run_id="run-1",
        name=agent_id,
        occupation="resident",
        profile={"world_role": world_role},
        personality={},
        status={},
        current_plan={},
    )


def test_manual_planner_returns_none_without_cast_agents():
    planner = ManualDirectorPlanner()

    plan = planner.build_plan_from_manual_event(
        event_type="broadcast",
        payload={"message": "everyone gather"},
        location_id="square",
        agents=[_make_agent("truman", "truman")],
        truman_agent_id="truman",
    )

    assert plan is None


def test_manual_planner_builds_gather_plan_for_broadcast():
    planner = ManualDirectorPlanner()

    plan = planner.build_plan_from_manual_event(
        event_type="broadcast",
        payload={"message": "meet at the square"},
        location_id="square",
        agents=[_make_agent("cast-a", "cast"), _make_agent("cast-b", "cast")],
        truman_agent_id="truman",
    )

    assert plan is not None
    assert plan.scene_goal == DIRECTOR_SCENE_GATHER
    assert plan.target_agent_ids == ["cast-a", "cast-b"]
    assert plan.target_cast_ids == ["cast-a", "cast-b"]
    assert plan.location_hint == "square"
    assert plan.target_agent_id == "truman"
    assert plan.message_hint == "meet at the square"
    assert plan.cooldown_ticks == 2


def test_manual_planner_builds_activity_shutdown_weather_and_power_outage_plans():
    planner = ManualDirectorPlanner()
    agents = [_make_agent("cast-a", "cast")]

    activity = planner.build_plan_from_manual_event(
        event_type="activity",
        payload={"message": "coffee party"},
        location_id="cafe",
        agents=agents,
        truman_agent_id="truman",
    )
    shutdown = planner.build_plan_from_manual_event(
        event_type="shutdown",
        payload={"message": "hospital closed"},
        location_id="hospital",
        agents=agents,
        truman_agent_id="truman",
    )
    weather = planner.build_plan_from_manual_event(
        event_type="weather_change",
        payload={"message": "heavy rain"},
        location_id="harbor",
        agents=agents,
        truman_agent_id="truman",
    )
    power_outage = planner.build_plan_from_manual_event(
        event_type="power_outage",
        payload={"message": "Block blackout"},
        location_id="harbor",
        agents=agents,
        truman_agent_id="truman",
    )

    assert activity is not None
    assert activity.scene_goal == DIRECTOR_SCENE_ACTIVITY
    assert activity.target_agent_ids == ["cast-a"]
    assert activity.priority == "high"
    assert activity.urgency == "immediate"

    assert shutdown is not None
    assert shutdown.scene_goal == DIRECTOR_SCENE_SHUTDOWN
    assert shutdown.location_hint == "hospital"
    assert shutdown.cooldown_ticks == 3

    assert weather is not None
    assert weather.scene_goal == DIRECTOR_SCENE_WEATHER_CHANGE
    assert weather.priority == "normal"
    assert weather.urgency == "advisory"

    assert power_outage is not None
    assert power_outage.scene_goal == DIRECTOR_SCENE_POWER_OUTAGE
    assert power_outage.location_hint == "harbor"
    assert power_outage.urgency == "immediate"


def test_manual_planner_returns_none_for_unsupported_event_type():
    planner = ManualDirectorPlanner()

    plan = planner.build_plan_from_manual_event(
        event_type="unknown",
        payload={"message": "ignored"},
        location_id=None,
        agents=[_make_agent("cast-a", "cast")],
        truman_agent_id="truman",
    )

    assert plan is None
