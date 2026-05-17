from __future__ import annotations
# ruff: noqa: F403,F405

from app.store.repository_modules._common import *


class MemoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_many(self, memories: Sequence[Memory]) -> Sequence[Memory]:
        memories = await self.add_many(memories)
        await self.session.commit()
        for memory in memories:
            await self.session.refresh(memory)
        return memories

    async def add_many(self, memories: Sequence[Memory]) -> Sequence[Memory]:
        self.session.add_all(list(memories))
        await self.session.flush()
        for memory in memories:
            await self.session.refresh(memory)
        return memories

    async def find_recent_routine_memory(
        self,
        run_id: str,
        agent_id: str,
        summary: str,
        location_id: str | None,
        since_tick: int,
    ) -> Memory | None:
        stmt: Select[tuple[Memory]] = (
            select(Memory)
            .where(
                Memory.run_id == run_id,
                Memory.agent_id == agent_id,
                Memory.summary == summary,
                Memory.location_id.is_(location_id)
                if location_id is None
                else Memory.location_id == location_id,
                Memory.metadata_json["event_type"].as_string().in_(["work", "rest"]),
                Memory.tick_no >= since_tick,
            )
            .order_by(Memory.tick_no.desc(), Memory.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
