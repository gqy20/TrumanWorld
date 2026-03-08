from __future__ import annotations

import pytest

from app.scenario.open_world.scenario import OpenWorldScenario
from app.scenario.truman_world.scenario import TrumanWorldScenario
from app.sim.world_loader import load_tick_data
from app.store.models import Agent, Event, Location, SimulationRun


@pytest.mark.asyncio
async def test_load_tick_data_preserves_location_and_agent_work_fields(db_session):
    run = SimulationRun(id="run-world-loader", name="world-loader", status="running")
    hospital = Location(
        id="run-world-loader-hospital",
        run_id=run.id,
        name="海湾医院",
        location_type="hospital",
        capacity=8,
    )
    spouse = Agent(
        id="run-world-loader-spouse",
        run_id=run.id,
        name="Meryl",
        occupation="医院职员",
        home_location_id=hospital.id,
        current_location_id=hospital.id,
        current_goal="work",
        personality={},
        profile={
            "agent_config_id": "spouse",
            "world_role": "cast",
            "workplace_location_id": hospital.id,
        },
        status={},
        current_plan={},
    )

    db_session.add_all([run, hospital, spouse])
    await db_session.commit()

    loaded = await load_tick_data(
        session=db_session,
        run_id=run.id,
        scenario=OpenWorldScenario(db_session),
    )

    location_state = loaded.world.locations[hospital.id]
    agent_state = loaded.world.agents[spouse.id]
    assert location_state.location_type == "hospital"
    assert agent_state.occupation == "医院职员"
    assert agent_state.workplace_id == hospital.id


@pytest.mark.asyncio
async def test_load_tick_data_includes_director_system_events_for_cast_only(db_session):
    run = SimulationRun(id="run-world-loader-director", name="director-recent", status="running")
    square = Location(
        id="run-world-loader-director-square",
        run_id=run.id,
        name="Town Square",
        location_type="plaza",
        capacity=10,
    )
    cast = Agent(
        id="run-world-loader-director-cast",
        run_id=run.id,
        name="Meryl",
        occupation="resident",
        home_location_id=square.id,
        current_location_id=square.id,
        current_goal="rest",
        personality={},
        profile={"agent_config_id": "spouse", "world_role": "cast"},
        status={},
        current_plan={},
    )
    truman = Agent(
        id="run-world-loader-director-truman",
        run_id=run.id,
        name="Truman",
        occupation="resident",
        home_location_id=square.id,
        current_location_id=square.id,
        current_goal="rest",
        personality={},
        profile={"agent_config_id": "truman", "world_role": "truman"},
        status={},
        current_plan={},
    )
    director_event = Event(
        id="evt-director-system",
        run_id=run.id,
        tick_no=1,
        event_type="director_broadcast",
        payload={"message": "Town hall at plaza"},
        visibility="system",
    )

    db_session.add_all([run, square, cast, truman, director_event])
    await db_session.commit()

    loaded = await load_tick_data(
        session=db_session,
        run_id=run.id,
        scenario=TrumanWorldScenario(db_session),
    )

    cast_snapshot = next(item for item in loaded.agent_data if item.id == cast.id)
    truman_snapshot = next(item for item in loaded.agent_data if item.id == truman.id)

    assert any(event["event_type"] == "director_broadcast" for event in cast_snapshot.recent_events)
    assert all(event["event_type"] != "director_broadcast" for event in truman_snapshot.recent_events)
