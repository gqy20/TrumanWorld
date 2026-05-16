from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from app.sim.persistence import PersistenceManager
from app.store.repositories import RunRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.sim.runner import TickResult
    from app.sim.world import WorldState
    from app.store.models import SimulationRun


PersistTickEvents = Callable[[str, "TickResult"], Awaitable[None]]


class TickPersistenceCoordinator:
    """Coordinates the database writes that must commit atomically for a tick."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        persistence: PersistenceManager | None = None,
        run_repo: RunRepository | None = None,
        persist_tick_events: PersistTickEvents,
    ) -> None:
        self.session = session
        self.persistence = persistence or PersistenceManager(session)
        self.run_repo = run_repo or RunRepository(session)
        self.persist_tick_events = persist_tick_events

    async def persist(
        self,
        *,
        run_id: str,
        run: SimulationRun,
        result: TickResult,
        world: WorldState,
    ) -> None:
        if self.session.in_transaction():
            await self.session.commit()

        async with self.session.begin():
            await self.persistence.set_agent_locations(run_id, world)
            await self.run_repo.set_tick(run, result.tick_no)
            await self.persist_tick_events(run_id, result)
