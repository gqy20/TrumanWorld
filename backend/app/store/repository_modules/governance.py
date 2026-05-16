from __future__ import annotations
# ruff: noqa: F403,F405

from app.store.repository_modules._common import *

class GovernanceRecordRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_many(self, records: Sequence[GovernanceRecord]) -> Sequence[GovernanceRecord]:
        records = await self.add_many(records)
        await self.session.commit()
        for record in records:
            await self.session.refresh(record)
        return records

    async def add_many(self, records: Sequence[GovernanceRecord]) -> Sequence[GovernanceRecord]:
        if not records:
            return []
        self.session.add_all(list(records))
        await self.session.flush()
        for record in records:
            await self.session.refresh(record)
        return records

    async def list_for_agent(
        self, run_id: str, agent_id: str, limit: int = 20
    ) -> Sequence[GovernanceRecord]:
        stmt: Select[tuple[GovernanceRecord]] = (
            select(GovernanceRecord)
            .where(
                GovernanceRecord.run_id == run_id,
                GovernanceRecord.agent_id == agent_id,
            )
            .order_by(GovernanceRecord.tick_no.desc(), GovernanceRecord.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_for_run(
        self,
        run_id: str,
        *,
        limit: int = 50,
        decision: str | None = None,
        agent_id: str | None = None,
    ) -> Sequence[GovernanceRecord]:
        stmt: Select[tuple[GovernanceRecord]] = select(GovernanceRecord).where(
            GovernanceRecord.run_id == run_id
        )
        if decision:
            stmt = stmt.where(GovernanceRecord.decision == decision)
        if agent_id:
            stmt = stmt.where(GovernanceRecord.agent_id == agent_id)
        stmt = stmt.order_by(
            GovernanceRecord.tick_no.desc(), GovernanceRecord.created_at.desc()
        ).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()


class GovernanceCaseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, case: GovernanceCase) -> GovernanceCase:
        self.session.add(case)
        await self.session.commit()
        await self.session.refresh(case)
        return case

    async def get_by_id(self, case_id: str) -> GovernanceCase | None:
        stmt: Select[tuple[GovernanceCase]] = select(GovernanceCase).where(
            GovernanceCase.id == case_id
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_for_agent(
        self,
        run_id: str,
        agent_id: str,
        limit: int = 20,
    ) -> Sequence[GovernanceCase]:
        stmt: Select[tuple[GovernanceCase]] = (
            select(GovernanceCase)
            .where(
                GovernanceCase.run_id == run_id,
                GovernanceCase.agent_id == agent_id,
            )
            .order_by(GovernanceCase.last_updated_tick.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_for_run(
        self,
        run_id: str,
        limit: int = 50,
    ) -> Sequence[GovernanceCase]:
        stmt: Select[tuple[GovernanceCase]] = (
            select(GovernanceCase)
            .where(GovernanceCase.run_id == run_id)
            .order_by(GovernanceCase.last_updated_tick.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_open_cases_for_agent(
        self,
        run_id: str,
        agent_id: str,
    ) -> Sequence[GovernanceCase]:
        stmt: Select[tuple[GovernanceCase]] = (
            select(GovernanceCase)
            .where(
                GovernanceCase.run_id == run_id,
                GovernanceCase.agent_id == agent_id,
                GovernanceCase.status.in_(["open", "warned", "restricted"]),
            )
            .order_by(GovernanceCase.last_updated_tick.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def find_mergeable_case(
        self,
        run_id: str,
        agent_id: str,
        primary_reason: str,
        current_tick: int,
        merge_window_ticks: int = 50,
    ) -> GovernanceCase | None:
        """Find an open case that can be merged with a new governance record.

        A case is mergeable if:
        - Same run_id, agent_id
        - Same primary_reason
        - Status is not 'closed'
        - Opened within merge_window_ticks of current_tick
        """
        min_tick = current_tick - merge_window_ticks
        stmt: Select[tuple[GovernanceCase]] = (
            select(GovernanceCase)
            .where(
                GovernanceCase.run_id == run_id,
                GovernanceCase.agent_id == agent_id,
                GovernanceCase.primary_reason == primary_reason,
                GovernanceCase.status != "closed",
                GovernanceCase.opened_tick >= min_tick,
            )
            .order_by(GovernanceCase.opened_tick.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def update_status(
        self,
        case_id: str,
        new_status: str,
        record_count: int | None = None,
        last_updated_tick: int | None = None,
    ) -> GovernanceCase | None:
        case = await self.get_by_id(case_id)
        if case is None:
            return None
        case.status = new_status
        if record_count is not None:
            case.record_count = record_count
        if last_updated_tick is not None:
            case.last_updated_tick = last_updated_tick
        await self.session.commit()
        await self.session.refresh(case)
        return case

    async def increment_record_count(
        self,
        case_id: str,
        tick_no: int,
    ) -> GovernanceCase | None:
        case = await self.get_by_id(case_id)
        if case is None:
            return None
        case.record_count += 1
        case.last_updated_tick = tick_no
        await self.session.commit()
        await self.session.refresh(case)
        return case


class GovernanceRestrictionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, restriction: GovernanceRestriction) -> GovernanceRestriction:
        self.session.add(restriction)
        await self.session.commit()
        await self.session.refresh(restriction)
        return restriction

    async def get_by_id(self, restriction_id: str) -> GovernanceRestriction | None:
        stmt: Select[tuple[GovernanceRestriction]] = select(GovernanceRestriction).where(
            GovernanceRestriction.id == restriction_id
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_active_for_agent(
        self,
        run_id: str,
        agent_id: str,
        tick_no: int | None = None,
    ) -> Sequence[GovernanceRestriction]:
        """List active restrictions for an agent at a given tick."""
        stmt = select(GovernanceRestriction).where(
            GovernanceRestriction.run_id == run_id,
            GovernanceRestriction.agent_id == agent_id,
            GovernanceRestriction.status == "active",
        )
        if tick_no is not None:
            stmt = stmt.where(
                or_(
                    GovernanceRestriction.end_tick.is_(None),
                    GovernanceRestriction.end_tick >= tick_no,
                )
            )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_for_case(
        self,
        case_id: str,
    ) -> Sequence[GovernanceRestriction]:
        stmt = select(GovernanceRestriction).where(GovernanceRestriction.case_id == case_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def has_active_restriction(
        self,
        run_id: str,
        agent_id: str,
        restriction_type: str,
        tick_no: int,
    ) -> bool:
        """Check if agent has an active restriction of given type at tick."""
        stmt = select(GovernanceRestriction).where(
            GovernanceRestriction.run_id == run_id,
            GovernanceRestriction.agent_id == agent_id,
            GovernanceRestriction.restriction_type == restriction_type,
            GovernanceRestriction.status == "active",
            GovernanceRestriction.start_tick <= tick_no,
            or_(
                GovernanceRestriction.end_tick.is_(None),
                GovernanceRestriction.end_tick >= tick_no,
            ),
        )
        result = await self.session.execute(stmt)
        return result.scalars().first() is not None

