from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

import app.sim.service as service_module
from app.sim.context import get_run_world_time
from app.sim.service import SimulationService
from app.store.models import Base
from app.store.repositories import EventRepository, RunRepository

from .helpers import build_rest_runtime, create_clock_run


@pytest.mark.asyncio
async def test_empty_run_tick_reports_database_activity(db_session, monkeypatch):
    run_id = "clock-empty-inline"
    await create_clock_run(
        db_session,
        run_id=run_id,
        current_tick=0,
        include_agent=False,
    )

    observations: list[dict] = []
    monkeypatch.setattr(
        service_module,
        "observe_database_operation",
        lambda **fields: observations.append(fields),
    )

    service = SimulationService(db_session)
    result = await service.run_tick(run_id)

    updated_run = await RunRepository(db_session).get(run_id)
    assert result.tick_no == 1
    assert result.tick_delta == 1
    assert result.accepted == []
    assert result.rejected == []
    assert result.world_time == "2026-03-02T06:05:00+00:00"
    assert updated_run is not None
    assert updated_run.current_tick == 1
    assert get_run_world_time(updated_run).isoformat() == "2026-03-02T06:05:00+00:00"
    assert len(observations) == 1
    assert observations[0]["operation"] == "tick.inline"
    assert 1 <= observations[0]["query_count"] <= 4
    assert observations[0]["duration_seconds"] >= 0


@pytest.mark.asyncio
async def test_inline_tick_commit_is_visible_to_new_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    run_id = "clock-inline-commit"
    async with AsyncSession(engine, expire_on_commit=False) as writer:
        await create_clock_run(writer, run_id=run_id, include_agent=False)
        await SimulationService(writer).run_tick(run_id)

    async with AsyncSession(engine, expire_on_commit=False) as reader:
        persisted = await RunRepository(reader).get(run_id)

    await engine.dispose()
    assert persisted is not None
    assert persisted.current_tick == 1


@pytest.mark.asyncio
async def test_empty_run_tick_skips_sleep_hours_without_ai(db_session):
    run_id = "clock-empty-skip"
    await create_clock_run(
        db_session,
        run_id=run_id,
        current_tick=203,
        include_agent=False,
    )

    service = SimulationService(db_session)
    result = await service.run_tick(run_id)

    updated_run = await RunRepository(db_session).get(run_id)
    events = await EventRepository(db_session).list_for_run(run_id)
    assert result.tick_no == 288
    assert result.tick_delta == 85
    assert result.accepted == []
    assert result.rejected == []
    assert result.world_time == "2026-03-03T06:00:00+00:00"
    assert updated_run is not None
    assert updated_run.current_tick == 288
    assert get_run_world_time(updated_run).isoformat() == "2026-03-03T06:00:00+00:00"
    assert list(events) == []


@pytest.mark.asyncio
async def test_rest_only_runtime_persists_event_and_reports_database_activity(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    run_id = "clock-rest-isolated"
    async with AsyncSession(engine, expire_on_commit=False) as session:
        await create_clock_run(
            session,
            run_id=run_id,
            current_tick=203,
            include_agent=True,
        )

    tmp_path = Path(tempfile.mkdtemp())
    runtime = build_rest_runtime(tmp_path)
    service = SimulationService.create_for_scheduler(runtime)
    observations: list[dict] = []
    monkeypatch.setattr(
        service_module,
        "observe_database_operation",
        lambda **fields: observations.append(fields),
    )

    try:
        result = await service.run_tick_isolated(run_id, engine)

        async with AsyncSession(engine, expire_on_commit=False) as session:
            run = await RunRepository(session).get(run_id)
            events = await EventRepository(session).list_for_run(run_id)

        assert result.tick_no == 288
        assert result.tick_delta == 85
        assert result.world_time == "2026-03-03T06:00:00+00:00"
        assert run is not None
        assert run.current_tick == 288
        assert get_run_world_time(run).isoformat() == "2026-03-03T06:00:00+00:00"
        assert len(events) == 1
        assert events[0].event_type == "rest"
        assert events[0].tick_no == 288
        assert len(observations) == 1
        assert observations[0]["operation"] == "tick.isolated"
        assert observations[0]["query_count"] > 0
    finally:
        await engine.dispose()
        shutil.rmtree(tmp_path)
