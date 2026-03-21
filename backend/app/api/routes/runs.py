from datetime import datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.auth import require_demo_admin_access
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.simulation import (
    COMMON_RESPONSES,
    RunCreateRequest,
    RunDetailResponse,
    RunResponse,
    StatusResponse,
    TickResponse,
)
from app.cognition.registry import get_cognition_registry
from app.infra.db import get_db_session
from app.infra.logging import get_logger
from app.scenario.bundle_registry import get_scenario_bundle_registry, resolve_default_scenario_id
from app.scenario.factory import create_scenario
from app.sim.run_lifecycle import ensure_run_started, pause_run_execution
from app.sim.scheduler import get_scheduler
from app.sim.service import SimulationService
from app.store.models import Agent, Event, Location, SimulationRun
from app.store.repositories import RunRepository

router = APIRouter()
logger = get_logger(__name__)


def build_run_payload(run: SimulationRun) -> dict[str, str | int | bool | datetime | None]:
    return {
        "id": run.id,
        "name": run.name,
        "status": run.status,
        "scenario_type": run.scenario_type,
        "current_tick": run.current_tick,
        "tick_minutes": run.tick_minutes,
        "was_running_before_restart": run.was_running_before_restart,
        "started_at": run.started_at,
        "elapsed_seconds": run.elapsed_seconds or 0,
        "created_at": run.created_at,
    }


def build_run_response(run: SimulationRun, **counts: int) -> RunResponse:
    return RunResponse(**build_run_payload(run), **counts)


def build_run_detail_response(run: SimulationRun) -> RunDetailResponse:
    return RunDetailResponse(**build_run_payload(run))


async def get_required_run(session: AsyncSession, run_id: UUID) -> SimulationRun:
    repo = RunRepository(session)
    run = await repo.get(str(run_id))
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return run


async def start_run_and_refresh(session: AsyncSession, run: SimulationRun) -> RunResponse:
    repo = RunRepository(session)
    updated = await ensure_run_started(session, run)
    await repo.clear_was_running_flag(updated)
    refreshed = await repo.get(updated.id)
    return build_run_response(refreshed or updated)


async def cleanup_run_runtime_resources(run_id: str) -> None:
    scheduler = get_scheduler()
    await scheduler.stop_run(run_id)
    await get_cognition_registry().cleanup_run(run_id)


@router.post(
    "",
    response_model=RunResponse,
    summary="创建新运行",
    description="创建一个新的 AI 模拟运行，可选择自动填充演示数据",
    responses={
        **COMMON_RESPONSES,
        201: {"description": "运行创建成功", "model": RunResponse},
    },
)
async def create_run(
    payload: RunCreateRequest,
    _: None = Depends(require_demo_admin_access),
    session: AsyncSession = Depends(get_db_session),
) -> RunResponse:
    logger.info(f"Creating new run: {payload.name}")
    scenario_type = payload.scenario_type or resolve_default_scenario_id()
    scenario_bundle = get_scenario_bundle_registry().get_bundle(scenario_type)
    if scenario_bundle is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown scenario_type: {scenario_type}",
        )
    repo = RunRepository(session)
    run = SimulationRun(
        id=str(uuid4()),
        name=payload.name,
        status="running",
        scenario_type=scenario_type,
        tick_minutes=payload.tick_minutes,
    )
    created = await repo.create(run)
    logger.info(f"Run created: id={created.id}, name={created.name}, auto-running")

    if payload.seed_demo:
        logger.debug(f"Seeding demo data for run {created.id}")
        service = SimulationService(
            session,
            scenario=create_scenario(created.scenario_type, session),
        )
        await service.seed_demo_run(created.id)
        logger.info(f"Demo data seeded for run {created.id}")

    created = await ensure_run_started(session, created)
    return build_run_response(created)


@router.get(
    "",
    response_model=list[RunResponse],
    summary="列出所有运行",
    description="获取所有模拟运行的列表",
    responses={
        **COMMON_RESPONSES,
        200: {"description": "运行列表", "model": list[RunResponse]},
    },
)
async def list_runs(
    session: AsyncSession = Depends(get_db_session),
) -> list[RunResponse]:
    logger.debug("Listing all runs")
    repo = RunRepository(session)
    runs = await repo.list()
    logger.debug(f"Found {len(runs)} runs")

    if not runs:
        return []

    run_ids = [run.id for run in runs]

    agent_counts_result = await session.execute(
        select(Agent.run_id, func.count(Agent.id).label("cnt"))
        .where(Agent.run_id.in_(run_ids))
        .group_by(Agent.run_id)
    )
    agent_counts: dict[str, int] = {row.run_id: row.cnt for row in agent_counts_result}

    location_counts_result = await session.execute(
        select(Location.run_id, func.count(Location.id).label("cnt"))
        .where(Location.run_id.in_(run_ids))
        .group_by(Location.run_id)
    )
    location_counts: dict[str, int] = {row.run_id: row.cnt for row in location_counts_result}

    event_counts_result = await session.execute(
        select(Event.run_id, func.count(Event.id).label("cnt"))
        .where(Event.run_id.in_(run_ids))
        .group_by(Event.run_id)
    )
    event_counts: dict[str, int] = {row.run_id: row.cnt for row in event_counts_result}

    return [
        build_run_response(
            run,
            agent_count=agent_counts.get(run.id, 0),
            location_count=location_counts.get(run.id, 0),
            event_count=event_counts.get(run.id, 0),
        )
        for run in runs
    ]


@router.post(
    "/restore-all",
    response_model=list[RunResponse],
    summary="恢复所有重启前的运行",
    description="恢复服务重启前正在运行的所有模拟运行，自动启动 tick 调度",
)
async def restore_all_runs(
    _: None = Depends(require_demo_admin_access),
    session: AsyncSession = Depends(get_db_session),
) -> list[RunResponse]:
    logger.info("Restore all runs requested")
    repo = RunRepository(session)
    runs_to_restore = await repo.list_runs_to_restore()

    if not runs_to_restore:
        logger.info("No runs to restore")
        return []

    restored: list[RunResponse] = []
    for run in runs_to_restore:
        try:
            updated = await ensure_run_started(session, run)
            await repo.clear_was_running_flag(updated)
            refreshed = await repo.get(updated.id)
            if refreshed is not None:
                restored.append(build_run_response(refreshed))
        except Exception as exc:
            logger.error(f"Failed to restore run {run.id}: {exc}")

    logger.info(f"Restored {len(restored)} runs")
    return restored


@router.post(
    "/{run_id}/start",
    response_model=RunResponse,
    summary="启动运行",
    description="启动模拟运行，开始自动 tick 调度",
)
async def start_run(
    run_id: UUID,
    _: None = Depends(require_demo_admin_access),
    session: AsyncSession = Depends(get_db_session),
) -> RunResponse:
    run = await get_required_run(session, run_id)
    return await start_run_and_refresh(session, run)


@router.post(
    "/{run_id}/pause",
    response_model=RunResponse,
    summary="暂停运行",
    description="暂停模拟运行，停止 tick 调度",
)
async def pause_run(
    run_id: UUID,
    _: None = Depends(require_demo_admin_access),
    session: AsyncSession = Depends(get_db_session),
) -> RunResponse:
    repo = RunRepository(session)
    run = await get_required_run(session, run_id)
    await pause_run_execution(str(run_id))
    updated = await repo.update_status(run, "paused")
    return build_run_response(updated)


@router.post(
    "/{run_id}/resume",
    response_model=RunResponse,
    summary="恢复运行",
    description="恢复已暂停的模拟运行",
)
async def resume_run(
    run_id: UUID,
    _: None = Depends(require_demo_admin_access),
    session: AsyncSession = Depends(get_db_session),
) -> RunResponse:
    run = await get_required_run(session, run_id)
    return await start_run_and_refresh(session, run)


@router.post(
    "/{run_id}/tick",
    response_model=TickResponse,
    summary="推进 Tick",
    description="手动推进模拟运行的一个 tick，执行 agent 动作和世界更新",
)
async def advance_run_tick(
    run_id: UUID,
    _: None = Depends(require_demo_admin_access),
    session: AsyncSession = Depends(get_db_session),
) -> TickResponse:
    logger.info(f"Advancing tick for run {run_id}")
    await get_required_run(session, run_id)

    service = SimulationService(session)
    result = await service.run_tick(str(run_id))
    logger.info(
        f"Tick {result.tick_no} completed: "
        f"accepted={len(result.accepted)}, rejected={len(result.rejected)}"
    )
    return TickResponse(
        run_id=str(run_id),
        tick_no=result.tick_no,
        accepted_count=len(result.accepted),
        rejected_count=len(result.rejected),
    )


@router.get(
    "/{run_id}",
    response_model=RunDetailResponse,
    summary="获取运行详情",
    description="获取指定模拟运行的详细状态信息",
)
async def get_run(
    run_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> RunDetailResponse:
    return build_run_detail_response(await get_required_run(session, run_id))


@router.delete(
    "/{run_id}",
    response_model=StatusResponse,
    summary="删除运行",
    description="""
**删除模拟运行**

删除指定运行及其所有关联数据（agents、locations、events、memories、relationships）。

这是一个破坏性操作，无法撤销。
    """,
)
async def delete_run(
    run_id: UUID,
    _: None = Depends(require_demo_admin_access),
    session: AsyncSession = Depends(get_db_session),
) -> StatusResponse:
    logger.info(f"Deleting run: {run_id}")
    run_id_str = str(run_id)
    await cleanup_run_runtime_resources(run_id_str)

    repo = RunRepository(session)
    run = await repo.get(run_id_str)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    await repo.delete_with_related(run)
    logger.info(f"Run deleted: {run_id}")
    return StatusResponse(run_id=run_id_str, status="deleted")
