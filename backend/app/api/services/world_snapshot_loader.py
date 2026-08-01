from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.store.repositories import (
    AgentRepository,
    EventRepository,
    LocationRepository,
    RunRepository,
    WorldStatsRepository,
)
from app.store.models import SimulationRun
from app.store.repository_modules._common import AgentWorldRow, EventApiRow, LocationWorldRow
from app.store.repository_modules.world_stats import WorldStats


@dataclass(slots=True)
class WorldSnapshotData:
    run: SimulationRun | None
    agents: Sequence[AgentWorldRow]
    locations: Sequence[LocationWorldRow]
    events: Sequence[EventApiRow]
    stats: WorldStats


async def load_world_snapshot_data(
    session: AsyncSession,
    run_id: str,
    *,
    event_limit: int,
) -> WorldSnapshotData:
    if _dialect_name(session) == "sqlite" or session.bind is None:
        return await _load_sequential(session, run_id, event_limit=event_limit)

    session_factory = async_sessionmaker(
        bind=session.bind,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    run, agents, locations, events, stats = await asyncio.gather(
        RunRepository(session).get(run_id),
        _load_isolated(
            session_factory,
            lambda isolated: AgentRepository(isolated).list_world_rows_for_run(run_id),
        ),
        _load_isolated(
            session_factory,
            lambda isolated: LocationRepository(isolated).list_world_rows_for_run(run_id),
        ),
        _load_isolated(
            session_factory,
            lambda isolated: EventRepository(isolated).list_api_rows_for_run(
                run_id,
                limit=event_limit,
            ),
        ),
        _load_isolated(
            session_factory,
            lambda isolated: WorldStatsRepository(isolated).get_for_run(run_id),
        ),
    )
    return WorldSnapshotData(
        run=run,
        agents=agents,
        locations=locations,
        events=events,
        stats=stats,
    )


async def _load_sequential(
    session: AsyncSession,
    run_id: str,
    *,
    event_limit: int,
) -> WorldSnapshotData:
    return WorldSnapshotData(
        run=await RunRepository(session).get(run_id),
        agents=await AgentRepository(session).list_world_rows_for_run(run_id),
        locations=await LocationRepository(session).list_world_rows_for_run(run_id),
        events=await EventRepository(session).list_api_rows_for_run(run_id, limit=event_limit),
        stats=await WorldStatsRepository(session).get_for_run(run_id),
    )


async def _load_isolated[T](
    session_factory: Callable[[], Any],
    loader: Callable[[AsyncSession], Awaitable[T]],
) -> T:
    async with session_factory() as session:
        return await loader(session)


def _dialect_name(session: AsyncSession) -> str | None:
    bind = session.bind
    if bind is None:
        return None
    return bind.dialect.name
