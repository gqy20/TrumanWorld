from __future__ import annotations

import asyncio

import pytest

from app.sim.scheduler import SimulationScheduler


@pytest.mark.asyncio
async def test_stop_run_cancels_inflight_callback_and_prevents_next_tick() -> None:
    scheduler = SimulationScheduler()
    tick_started = asyncio.Event()
    callback_cancelled = asyncio.Event()
    ticks: list[str] = []

    async def callback(run_id: str) -> None:
        ticks.append(run_id)
        tick_started.set()
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            callback_cancelled.set()
            raise

    await scheduler.start_run("run-1", interval_seconds=0.01, callback=callback)
    await asyncio.wait_for(tick_started.wait(), timeout=1.0)

    await scheduler.stop_run("run-1")

    await asyncio.wait_for(callback_cancelled.wait(), timeout=1.0)
    await asyncio.sleep(0.05)

    assert ticks == ["run-1"]
    assert not scheduler.is_running("run-1")


@pytest.mark.asyncio
async def test_stop_run_before_first_tick_prevents_auto_advance() -> None:
    scheduler = SimulationScheduler()
    ticks: list[str] = []

    async def callback(run_id: str) -> None:
        ticks.append(run_id)

    await scheduler.start_run("run-2", interval_seconds=0.2, callback=callback)
    await scheduler.stop_run("run-2")
    await asyncio.sleep(0.25)

    assert ticks == []
    assert not scheduler.is_running("run-2")
