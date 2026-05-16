from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.sim.action_resolver import ActionResult
from app.sim.runner import TickResult
from app.sim.tick_event_writer import TickEventWriter
from app.store.models import Agent, Event, Location, SimulationRun

from .test_service import FakeScenario


@pytest.mark.asyncio
async def test_persist_rolls_back_events_when_followup_persistence_fails(db_session):
    run = SimulationRun(
        id="run-writer-atomic",
        name="writer-atomic",
        status="running",
        current_tick=0,
        tick_minutes=5,
    )
    home = Location(
        id="loc-writer-atomic",
        run_id=run.id,
        name="Home",
        location_type="home",
        capacity=2,
    )
    alice = Agent(
        id="alice-writer-atomic",
        run_id=run.id,
        name="Alice",
        occupation="resident",
        home_location_id=home.id,
        current_location_id=home.id,
        personality={},
        profile={},
        status={},
        current_plan={},
    )
    db_session.add_all([run, home, alice])
    await db_session.commit()
    run_id = run.id

    writer = TickEventWriter(db_session)
    assert writer.persistence is not None

    async def fail_memories(*_args, **_kwargs):
        raise RuntimeError("memory write failed")

    writer.persistence.persist_tick_memories = fail_memories
    scenario = FakeScenario()
    result = TickResult(
        tick_no=1,
        world_time=datetime(2026, 3, 2, 6, 5, tzinfo=UTC).isoformat(),
        tick_delta=1,
        accepted=[
            ActionResult(
                accepted=True,
                action_type="rest",
                reason="accepted",
                event_payload={"agent_id": alice.id, "location_id": home.id},
            )
        ],
        rejected=[],
    )

    with pytest.raises(RuntimeError, match="memory write failed"):
        await writer.persist(run_id=run_id, result=result, scenario=scenario)

    await db_session.rollback()
    persisted_events = (
        (await db_session.execute(select(Event).where(Event.run_id == run_id))).scalars().all()
    )

    assert persisted_events == []
    assert scenario.state_update_calls == []
