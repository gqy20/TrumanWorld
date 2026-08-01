from __future__ import annotations

import asyncio
from time import monotonic

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

import app.api.services.world_snapshot_loader as loader_module
from app.api.services.world_snapshot_loader import _load_isolated, load_world_snapshot_data
from app.store.repositories import (
    AgentRepository,
    EventRepository,
    LocationRepository,
    RunRepository,
    WorldStatsRepository,
)


class _FakeSessionContext:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, *_args):
        return None


@pytest.mark.asyncio
async def test_isolated_world_snapshot_queries_can_run_concurrently():
    async def slow_loader(_session):
        await asyncio.sleep(0.05)
        return "loaded"

    started = monotonic()
    results = await asyncio.gather(
        *(_load_isolated(_FakeSessionContext, slow_loader) for _ in range(4))
    )

    assert results == ["loaded"] * 4
    assert monotonic() - started < 0.15


@pytest.mark.asyncio
async def test_postgres_world_snapshot_loader_parallelizes_all_read_groups(monkeypatch):
    async def slow_loader(*_args, **_kwargs):
        await asyncio.sleep(0.05)
        return "loaded"

    for repository, method_name in (
        (RunRepository, "get"),
        (AgentRepository, "list_world_rows_for_run"),
        (LocationRepository, "list_world_rows_for_run"),
        (EventRepository, "list_api_rows_for_run"),
        (WorldStatsRepository, "get_for_run"),
    ):
        monkeypatch.setattr(repository, method_name, slow_loader)
    monkeypatch.setattr(loader_module, "_dialect_name", lambda _session: "postgresql")

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with AsyncSession(engine) as session:
            started = monotonic()
            result = await load_world_snapshot_data(session, "run-1", event_limit=60)
            elapsed = monotonic() - started
    finally:
        await engine.dispose()

    assert result.run == "loaded"
    assert result.agents == "loaded"
    assert result.locations == "loaded"
    assert result.events == "loaded"
    assert result.stats == "loaded"
    assert elapsed < 0.15
