from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.connection_pool import get_connection_pool
from app.agent.registry import AgentRegistry
from app.agent.runtime import AgentRuntime
from app.infra.db import async_engine
from app.infra.logging import get_logger
from app.infra.settings import get_settings
from app.scenario.factory import create_scenario
from app.scenario.types import get_agent_config_id
from app.sim.service import SimulationService
from app.store.models import SimulationRun
from app.store.repositories import AgentRepository, RunRepository


logger = get_logger(__name__)


@dataclass
class RunExecutionPlan:
    interval_seconds: float
    tick_callback: Callable[[str], Awaitable[None]]
    on_max_errors: Callable[[str], Awaitable[None]] | None = None


class RunExecutionBootstrapper:
    async def prepare(self, session: AsyncSession, run: SimulationRun) -> RunExecutionPlan:
        settings = get_settings()
        registry = AgentRegistry(settings.project_root / "agents")
        pool = await get_connection_pool()
        await self._warm_connection_pool(session, run.id, pool)
        agent_runtime = AgentRuntime(registry=registry, connection_pool=pool)
        scenario = create_scenario(run.scenario_type)

        async def tick_callback(run_id: str) -> None:
            service = SimulationService.create_for_scheduler(agent_runtime, scenario=scenario)
            await service.run_tick_isolated(run_id, async_engine)
            if hasattr(pool, "cleanup_idle"):
                await pool.cleanup_idle()

        async def on_max_errors(run_id: str) -> None:
            """连续失败超过阈值时自动暂停 run，更新数据库状态。"""
            logger.warning(
                f"Auto-pausing run {run_id} due to consecutive tick failures "
                f"(max={settings.scheduler_max_consecutive_errors})"
            )
            async with AsyncSession(async_engine, expire_on_commit=False) as session:
                run = await session.get(SimulationRun, run_id)
                if run is not None:
                    await RunRepository(session).update_status(run, "paused")
                    logger.info(f"Run {run_id} auto-paused after consecutive errors")

        return RunExecutionPlan(
            interval_seconds=settings.scheduler_interval_seconds,
            tick_callback=tick_callback,
            on_max_errors=on_max_errors,
        )

    async def _warm_connection_pool(self, session: AsyncSession, run_id: str, pool) -> None:
        agents = await AgentRepository(session).list_for_run(run_id)
        pool_keys = sorted(
            {f"{run_id}:{get_agent_config_id(agent.profile) or agent.id}" for agent in agents}
        )
        if pool_keys:
            await pool.warmup(pool_keys)
