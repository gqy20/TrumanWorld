from __future__ import annotations
# ruff: noqa: F403,F405

from app.store.repository_modules._common import *


class RunRepository:
    """Persistence facade for simulation runs."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, run: SimulationRun) -> SimulationRun:
        self.session.add(run)
        await self.session.flush()
        await self.session.refresh(run)
        return run

    async def create(self, run: SimulationRun) -> SimulationRun:
        await self.add(run)
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def get(self, run_id: str) -> SimulationRun | None:
        return await self.session.get(SimulationRun, run_id)

    async def list(self, limit: int = 20) -> Sequence[SimulationRun]:
        stmt: Select[tuple[SimulationRun]] = (
            select(SimulationRun)
            .order_by(SimulationRun.updated_at.desc(), SimulationRun.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update_status(self, run: SimulationRun, status: str) -> SimulationRun:
        now = datetime.now(UTC)
        if status == "running":
            # 开始运行：记录本次启动时间（仅当之前未启动时才设置，避免恢复时重置）
            if run.started_at is None:
                run.started_at = now
        elif run.started_at is not None:
            # 暂停/停止：把本次运行时长累加到 elapsed_seconds
            delta = int((now - run.started_at).total_seconds())
            run.elapsed_seconds = (run.elapsed_seconds or 0) + max(0, delta)
            run.started_at = None
        run.status = status
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def update_tick(self, run: SimulationRun, tick_no: int) -> SimulationRun:
        await self.set_tick(run, tick_no)
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def set_tick(self, run: SimulationRun, tick_no: int) -> SimulationRun:
        run.current_tick = tick_no
        await self.session.flush()
        await self.session.refresh(run)
        return run

    async def delete(self, run: SimulationRun) -> None:
        await self.session.delete(run)
        await self.session.commit()

    async def delete_with_related(self, run: SimulationRun) -> None:
        run_id = run.id
        await self.session.execute(delete(Relationship).where(Relationship.run_id == run_id))
        await self.session.execute(
            delete(GovernanceRestriction).where(GovernanceRestriction.run_id == run_id)
        )
        await self.session.execute(delete(GovernanceCase).where(GovernanceCase.run_id == run_id))
        await self.session.execute(
            delete(GovernanceRecord).where(GovernanceRecord.run_id == run_id)
        )
        await self.session.execute(
            delete(EconomicEffectLog).where(EconomicEffectLog.run_id == run_id)
        )
        await self.session.execute(
            delete(AgentEconomicState).where(AgentEconomicState.run_id == run_id)
        )
        await self.session.execute(delete(Memory).where(Memory.run_id == run_id))
        await self.session.execute(delete(DirectorMemory).where(DirectorMemory.run_id == run_id))
        await self.session.execute(delete(Event).where(Event.run_id == run_id))
        await self.session.execute(delete(LlmCall).where(LlmCall.run_id == run_id))
        await self.session.execute(delete(Agent).where(Agent.run_id == run_id))
        await self.session.execute(delete(Location).where(Location.run_id == run_id))
        await self.session.delete(run)
        await self.session.commit()

    async def reset_running_on_startup(self) -> list[SimulationRun]:
        """Reset all running runs to paused on startup.

        Sets was_running_before_restart=True for runs that were running,
        accumulates elapsed time from started_at to now, then sets status
        to 'paused'. Returns the list of affected runs.
        """
        from datetime import UTC, datetime

        from sqlalchemy import update

        now = datetime.now(UTC)

        # First, get all running runs
        stmt = select(SimulationRun).where(SimulationRun.status == "running")
        result = await self.session.execute(stmt)
        running_runs = list(result.scalars().all())

        if not running_runs:
            return []

        # Accumulate elapsed time for each run before pausing
        run_updates = []
        for run in running_runs:
            new_elapsed = run.elapsed_seconds or 0
            if run.started_at is not None:
                delta = int((now - run.started_at).total_seconds())
                new_elapsed += max(0, delta)
            run_updates.append(
                {
                    "id": run.id,
                    "elapsed_seconds": new_elapsed,
                }
            )

        # Update: set was_running_before_restart=True, status='paused',
        # elapsed_seconds=accumulated, started_at=None
        for upd in run_updates:
            await self.session.execute(
                update(SimulationRun)
                .where(SimulationRun.id == upd["id"])
                .values(
                    was_running_before_restart=True,
                    status="paused",
                    elapsed_seconds=upd["elapsed_seconds"],
                    started_at=None,
                )
            )
        await self.session.commit()

        # Refresh and return
        for run in running_runs:
            await self.session.refresh(run)
        return running_runs

    async def list_runs_to_restore(self) -> Sequence[SimulationRun]:
        """Get all runs that were running before restart and can be restored."""
        stmt = select(SimulationRun).where(
            SimulationRun.was_running_before_restart.is_(True),
            SimulationRun.status == "paused",
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def clear_was_running_flag(self, run: SimulationRun) -> SimulationRun:
        """Clear the was_running_before_restart flag after successful restore."""
        run.was_running_before_restart = False
        await self.session.commit()
        await self.session.refresh(run)
        return run
