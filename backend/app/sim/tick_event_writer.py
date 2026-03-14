from __future__ import annotations

from typing import TYPE_CHECKING

from app.sim.event_utils import build_event
from app.sim.persistence import PersistenceManager

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.scenario.base import Scenario
    from app.sim.runner import TickResult
    from app.store.models import Event


class TickEventWriter:
    def __init__(self, session: AsyncSession | None) -> None:
        self.persistence = PersistenceManager(session) if session is not None else None

    async def persist(
        self,
        *,
        run_id: str,
        result: TickResult,
        scenario: Scenario,
    ) -> list[Event]:
        if self.persistence is None:
            msg = "TickEventWriter.persist requires a bound session"
            raise RuntimeError(msg)

        events = [
            build_event(
                run_id=run_id,
                tick_no=result.tick_no,
                world_time=result.world_time,
                action_type=item.action_type,
                payload=item.event_payload,
                accepted=True,
            )
            for item in result.accepted
        ]
        events.extend(
            build_event(
                run_id=run_id,
                tick_no=result.tick_no,
                world_time=result.world_time,
                action_type=item.action_type,
                payload={"reason": item.reason, **item.event_payload},
                accepted=False,
            )
            for item in result.rejected
        )
        if not events:
            return []

        persisted = await self.persistence.event_repo.create_many(events)
        await self.persistence.persist_tick_memories(run_id, persisted)
        await self.persistence.persist_tick_relationships(run_id, persisted)
        await scenario.update_state_from_events(run_id, persisted)
        return persisted
