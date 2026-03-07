import pytest

from app.sim.action_resolver import ActionIntent
from app.sim.service import SimulationService
from app.store.models import Agent, Location, SimulationRun
from app.store.repositories import EventRepository, RunRepository


@pytest.mark.asyncio
async def test_simulation_service_persists_tick_and_events(db_session):
    run = SimulationRun(id="run-service-1", name="service", status="running", current_tick=0, tick_minutes=5)
    home = Location(id="loc-home", run_id="run-service-1", name="Home", location_type="home", capacity=2)
    park = Location(id="loc-park", run_id="run-service-1", name="Park", location_type="park", capacity=2)
    alice = Agent(
        id="alice",
        run_id="run-service-1",
        name="Alice",
        occupation="resident",
        home_location_id="loc-home",
        current_location_id="loc-home",
        personality={},
        profile={},
        status={},
        current_plan={},
    )

    db_session.add_all([run, home, park, alice])
    await db_session.commit()

    service = SimulationService(db_session)
    result = await service.run_tick(
        "run-service-1",
        [ActionIntent(agent_id="alice", action_type="move", target_location_id="loc-park")],
    )

    run_repo = RunRepository(db_session)
    event_repo = EventRepository(db_session)
    updated_run = await run_repo.get("run-service-1")
    events = await event_repo.list_for_run("run-service-1")

    assert result.tick_no == 1
    assert updated_run is not None
    assert updated_run.current_tick == 1
    assert len(events) == 1
    assert events[0].event_type == "move"
    assert events[0].payload["to_location_id"] == "loc-park"


@pytest.mark.asyncio
async def test_simulation_service_persists_rejected_events(db_session):
    run = SimulationRun(id="run-service-2", name="service", status="running", current_tick=0, tick_minutes=5)
    home = Location(id="loc-home-2", run_id="run-service-2", name="Home", location_type="home", capacity=2)
    alice = Agent(
        id="alice-2",
        run_id="run-service-2",
        name="Alice",
        occupation="resident",
        home_location_id="loc-home-2",
        current_location_id="loc-home-2",
        personality={},
        profile={},
        status={},
        current_plan={},
    )

    db_session.add_all([run, home, alice])
    await db_session.commit()

    service = SimulationService(db_session)
    result = await service.run_tick(
        "run-service-2",
        [ActionIntent(agent_id="alice-2", action_type="move", target_location_id="missing-location")],
    )

    event_repo = EventRepository(db_session)
    events = await event_repo.list_for_run("run-service-2")

    assert result.tick_no == 1
    assert len(result.rejected) == 1
    assert len(events) == 1
    assert events[0].event_type == "move_rejected"
    assert events[0].payload["reason"] == "location_not_found"


@pytest.mark.asyncio
async def test_simulation_service_can_prepare_intents_from_agent_runtime(db_session):
    run = SimulationRun(id="run-service-3", name="service", status="running", current_tick=0, tick_minutes=5)
    home = Location(id="loc-home-3", run_id="run-service-3", name="Home", location_type="home", capacity=2)
    park = Location(id="loc-park-3", run_id="run-service-3", name="Park", location_type="park", capacity=2)
    alice = Agent(
        id="demo_agent",
        run_id="run-service-3",
        name="Demo Agent",
        occupation="resident",
        home_location_id="loc-home-3",
        current_location_id="loc-home-3",
        current_goal="move:loc-park-3",
        personality={},
        profile={},
        status={},
        current_plan={},
    )

    db_session.add_all([run, home, park, alice])
    await db_session.commit()

    service = SimulationService(db_session)
    result = await service.run_tick("run-service-3")

    event_repo = EventRepository(db_session)
    events = await event_repo.list_for_run("run-service-3")

    assert result.tick_no == 1
    assert len(result.accepted) == 1
    assert result.accepted[0].action_type == "move"
    assert len(events) == 1
    assert events[0].event_type == "move"
