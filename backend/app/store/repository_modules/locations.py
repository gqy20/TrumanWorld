from __future__ import annotations
# ruff: noqa: F403,F405

from app.store.repository_modules._common import *


class LocationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_run(self, run_id: str) -> Sequence[Location]:
        stmt: Select[tuple[Location]] = (
            select(Location).where(Location.run_id == run_id).order_by(Location.name.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_names_for_run(self, run_id: str) -> Sequence[LocationNameRow]:
        stmt = (
            select(Location.id, Location.name)
            .where(Location.run_id == run_id)
            .order_by(Location.name.asc())
        )
        result = await self.session.execute(stmt)
        return [LocationNameRow(id=row.id, name=row.name) for row in result.all()]

    async def list_world_rows_for_run(self, run_id: str) -> Sequence[LocationWorldRow]:
        stmt = (
            select(
                Location.id,
                Location.name,
                Location.location_type,
                Location.x,
                Location.y,
                Location.capacity,
            )
            .where(Location.run_id == run_id)
            .order_by(Location.name.asc())
        )
        result = await self.session.execute(stmt)
        return [
            LocationWorldRow(
                id=row.id,
                name=row.name,
                location_type=row.location_type,
                x=row.x,
                y=row.y,
                capacity=row.capacity,
            )
            for row in result.all()
        ]
