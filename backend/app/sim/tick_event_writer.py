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

        if self.persistence.session.in_transaction():
            return await self._persist_events_in_transaction(
                run_id=run_id,
                events=events,
                scenario=scenario,
            )

        async with self.persistence.session.begin():
            return await self._persist_events_in_transaction(
                run_id=run_id,
                events=events,
                scenario=scenario,
            )

    async def _persist_events_in_transaction(
        self,
        *,
        run_id: str,
        events: list[Event],
        scenario: Scenario,
    ) -> list[Event]:
        if self.persistence is None:
            msg = "TickEventWriter.persist requires a bound session"
            raise RuntimeError(msg)

        transaction_depth_key = "tick_event_writer_transaction_depth"
        session_info = self.persistence.session.info
        previous_depth = int(session_info.get(transaction_depth_key, 0))
        session_info[transaction_depth_key] = previous_depth + 1
        try:
            persisted = list(await self.persistence.event_repo.add_many(events))
            await self.persistence.persist_tick_memories(run_id, persisted)
            await self.persistence.persist_tick_relationships(run_id, persisted)
            await scenario.update_state_from_events(run_id, persisted)
            return persisted
        finally:
            if previous_depth:
                session_info[transaction_depth_key] = previous_depth
            else:
                session_info.pop(transaction_depth_key, None)
