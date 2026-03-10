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
from app.store.repositories import AgentRepository


logger = get_logger(__name__)


@dataclass
class RunExecutionPlan:
    interval_seconds: float
    tick_callback: Callable[[str], Awaitable[None]]


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

        return RunExecutionPlan(
            interval_seconds=settings.scheduler_interval_seconds,
            tick_callback=tick_callback,
        )

    async def _warm_connection_pool(self, session: AsyncSession, run_id: str, pool) -> None:
        agents = await AgentRepository(session).list_for_run(run_id)
        pool_keys = sorted(
            {f"{run_id}:{get_agent_config_id(agent.profile) or agent.id}" for agent in agents}
        )
        if not pool_keys:
            return

        logger.info(f"Warming up connection pool for run {run_id}: {pool_keys}")
        await pool.warmup(pool_keys)
