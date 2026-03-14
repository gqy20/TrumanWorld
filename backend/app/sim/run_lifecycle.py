from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.cognition.registry import get_cognition_registry
from app.infra.logging import get_logger
from app.sim.bootstrap import RunExecutionBootstrapper
from app.sim.scheduler import get_scheduler
from app.store.models import SimulationRun
from app.store.repositories import RunRepository

logger = get_logger(__name__)


async def ensure_run_started(session: AsyncSession, run: SimulationRun) -> SimulationRun:
    scheduler = get_scheduler()
    if scheduler.is_running(run.id):
        if run.status != "running":
            return await RunRepository(session).update_status(run, "running")
        return run

    plan = await RunExecutionBootstrapper().prepare(session, run)
    start_kwargs = {
        "interval_seconds": plan.interval_seconds,
        "callback": plan.tick_callback,
    }
    on_max_errors = getattr(plan, "on_max_errors", None)
    if on_max_errors is not None:
        start_kwargs["on_max_errors"] = on_max_errors
    await scheduler.start_run(run.id, **start_kwargs)

    if run.status != "running":
        return await RunRepository(session).update_status(run, "running")
    return run


async def pause_run_execution(run_id: str) -> None:
    scheduler = get_scheduler()
    logger.info(f"Pause run requested for {run_id}, stopping scheduler")
    await scheduler.stop_run(run_id)
    await get_cognition_registry().cleanup_run(run_id)
