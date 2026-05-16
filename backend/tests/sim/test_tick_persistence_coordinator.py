from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from app.sim.runner import TickResult
from app.sim.tick_persistence_coordinator import TickPersistenceCoordinator
from app.sim.world import WorldState
from app.store.models import SimulationRun


class FailingLocationPersistence:
    async def set_agent_locations(self, *_args, **_kwargs) -> None:
        raise RuntimeError("location persistence failed")


@pytest.mark.asyncio
async def test_persist_does_not_write_events_when_location_persistence_fails(db_session):
    run = SimulationRun(
        id="run-coordinator-location-fails",
        name="coordinator-location-fails",
        status="running",
        current_tick=0,
        tick_minutes=5,
    )
    db_session.add(run)
    await db_session.commit()
    run_id = run.id

    persist_tick_events = AsyncMock()
    coordinator = TickPersistenceCoordinator(
        db_session,
        persistence=FailingLocationPersistence(),
        persist_tick_events=persist_tick_events,
    )
    result = TickResult(
        tick_no=1,
        world_time=datetime(2026, 3, 2, 6, 5, tzinfo=UTC).isoformat(),
        tick_delta=1,
        accepted=[],
        rejected=[],
    )
    world = WorldState(current_time=datetime(2026, 3, 2, 6, 0, tzinfo=UTC), current_tick=0)

    with pytest.raises(RuntimeError, match="location persistence failed"):
        await coordinator.persist(run_id=run_id, run=run, result=result, world=world)

    await db_session.rollback()
    refreshed_run = await db_session.get(SimulationRun, run_id)

    assert refreshed_run is not None
    assert refreshed_run.current_tick == 0
    persist_tick_events.assert_not_awaited()


@pytest.mark.asyncio
async def test_persist_reuses_existing_transaction_without_committing_pending_changes(db_session):
    run = SimulationRun(
        id="run-coordinator-existing-transaction",
        name="original",
        status="running",
        current_tick=0,
        tick_minutes=5,
    )
    db_session.add(run)
    await db_session.commit()
    run_id = run.id

    run.name = "pending-change"

    async def fail_tick_events(*_args, **_kwargs) -> None:
        raise RuntimeError("event persistence failed")

    coordinator = TickPersistenceCoordinator(
        db_session,
        persist_tick_events=fail_tick_events,
    )
    result = TickResult(
        tick_no=1,
        world_time=datetime(2026, 3, 2, 6, 5, tzinfo=UTC).isoformat(),
        tick_delta=1,
        accepted=[],
        rejected=[],
    )
    world = WorldState(current_time=datetime(2026, 3, 2, 6, 0, tzinfo=UTC), current_tick=0)

    with pytest.raises(RuntimeError, match="event persistence failed"):
        await coordinator.persist(run_id=run_id, run=run, result=result, world=world)

    await db_session.rollback()
    refreshed_run = await db_session.get(SimulationRun, run_id)

    assert refreshed_run is not None
    assert refreshed_run.name == "original"
    assert refreshed_run.current_tick == 0
