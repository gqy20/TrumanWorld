from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.registry import AgentRegistry
from app.agent.runtime import AgentRuntime
from app.cognition.registry import get_cognition_registry
from app.infra.db import async_engine
from app.infra.logging import get_logger
from app.infra.settings import get_settings
from app.scenario.factory import create_scenario
from app.sim.service import SimulationService
from app.store.models import SimulationRun
from app.store.repositories import RunRepository

logger = get_logger(__name__)


@dataclass
class RunExecutionPlan:
    interval_seconds: float
    tick_callback: Callable[[str], Awaitable[None]]
    on_max_errors: Callable[[str], Awaitable[None]] | None = None


class RunExecutionBootstrapper:
    async def prepare(self, session: AsyncSession, run: SimulationRun) -> RunExecutionPlan:
        settings = get_settings()
        agent_registry = AgentRegistry(settings.project_root / "agents")
        cognition_registry = get_cognition_registry()
        if bool(getattr(settings, "claude_sdk_reactor_pool_enabled", True)):
            await cognition_registry.warmup_for_run(session, run.id)
        agent_runtime = AgentRuntime(
            registry=agent_registry,
            cognition_registry=cognition_registry,
        )
        scenario = create_scenario(run.scenario_type)

        async def tick_callback(run_id: str) -> None:
            service = SimulationService.create_for_scheduler(agent_runtime, scenario=scenario)
            await service.run_tick_isolated(run_id, async_engine)
            await cognition_registry.cleanup_idle()

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
