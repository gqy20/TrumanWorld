import asyncio

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from app.sim.errors import TickInProgressError
from app.sim.tick_lock import acquire_run_tick_lock


@pytest.mark.asyncio
async def test_local_tick_lock_rejects_overlapping_tick_for_same_run() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    first_entered = asyncio.Event()
    release_first = asyncio.Event()

    async def hold_first_lock() -> None:
        async with acquire_run_tick_lock(engine, "run-1"):
            first_entered.set()
            await release_first.wait()

    first = asyncio.create_task(hold_first_lock())
    await first_entered.wait()

    with pytest.raises(TickInProgressError, match="run-1"):
        async with acquire_run_tick_lock(engine, "run-1"):
            pass

    release_first.set()
    await first
    await engine.dispose()


@pytest.mark.asyncio
async def test_local_tick_locks_are_scoped_per_run() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async with acquire_run_tick_lock(engine, "run-1"):
        async with acquire_run_tick_lock(engine, "run-2"):
            pass

    await engine.dispose()
