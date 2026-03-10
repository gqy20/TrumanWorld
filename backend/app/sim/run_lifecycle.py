from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.connection_pool import get_connection_pool
from app.agent.registry import AgentRegistry
from app.agent.runtime import AgentRuntime
from app.infra.db import async_engine
from app.infra.logging import get_logger
from app.infra.settings import get_settings
from app.scenario.types import get_agent_config_id
from app.sim.scheduler import get_scheduler
from app.sim.service import SimulationService
from app.store.models import SimulationRun
from app.store.repositories import AgentRepository, RunRepository


logger = get_logger(__name__)


async def ensure_run_started(session: AsyncSession, run: SimulationRun) -> SimulationRun:
    scheduler = get_scheduler()
    if scheduler.is_running(run.id):
        if run.status != "running":
            return await RunRepository(session).update_status(run, "running")
        return run

    settings = get_settings()
    registry = AgentRegistry(settings.project_root / "agents")
    pool = await get_connection_pool()

    agent_repo = AgentRepository(session)
    agents = await agent_repo.list_for_run(run.id)
    pool_keys = set()
    for agent in agents:
        config_id = get_agent_config_id(agent.profile)
        agent_key = config_id if config_id else agent.id
        pool_keys.add(f"{run.id}:{agent_key}")

    if pool_keys:
        logger.info(f"Warming up connection pool for run {run.id}: {pool_keys}")
        await pool.warmup(list(pool_keys))

    agent_runtime = AgentRuntime(registry=registry, connection_pool=pool)
    scenario = SimulationService.build_scenario(run.scenario_type)

    async def tick_callback(rid: str) -> None:
        service = SimulationService.create_for_scheduler(agent_runtime, scenario=scenario)
        await service.run_tick_isolated(rid, async_engine)

    await scheduler.start_run(run.id, interval_seconds=5.0, callback=tick_callback)

    if run.status != "running":
        return await RunRepository(session).update_status(run, "running")
    return run


async def pause_run_execution(run_id: str) -> None:
    scheduler = get_scheduler()
    logger.info(f"Pause run requested for {run_id}, stopping scheduler")
    await scheduler.stop_run(run_id)

    pool = await get_connection_pool()
    await pool.cleanup_run(run_id)
