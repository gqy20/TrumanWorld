from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db import get_db_session
from app.infra.logging import get_logger
from app.sim.context import get_run_world_time
from app.sim.scheduler import get_scheduler
from app.sim.service import SimulationService
from app.store.models import SimulationRun
from app.store.repositories import (
    AgentRepository,
    EventRepository,
    LocationRepository,
    RunRepository,
)

router = APIRouter()
logger = get_logger(__name__)


class RunCreateRequest(BaseModel):
    """创建新的模拟运行请求"""

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="运行名称",
        examples=["My First World", "Alice Town"],
    )
    seed_demo: bool = Field(
        default=True,
        description="是否自动填充演示数据（agent、地点等）",
        examples=[True],
    )


class RunResponse(BaseModel):
    """模拟运行响应"""

    id: UUID = Field(..., description="运行 ID")
    name: str = Field(..., description="运行名称")
    status: str = Field(..., description="运行状态", examples=["running", "paused", "stopped"])
    current_tick: int | None = Field(None, description="当前 tick 数")
    tick_minutes: int | None = Field(None, description="每个 tick 代表的分钟数")
    was_running_before_restart: bool = Field(
        False, description="服务重启前是否在运行中（用于一键恢复）"
    )


class DirectorEventRequest(BaseModel):
    """导演事件注入请求"""

    event_type: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="事件类型",
        examples=["activity", "shutdown", "broadcast", "weather_change"],
    )
    payload: dict = Field(
        default_factory=dict,
        description="事件负载数据",
        examples=[{"message": "咖啡馆举办周末派对", "duration_hours": 2}],
    )
    location_id: str | None = Field(
        None,
        description="事件发生地点 ID",
        examples=["downtown_cafe"],
    )
    importance: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="事件重要性（0-1）",
        examples=[0.8],
    )


class TickResponse(BaseModel):
    """Tick 推进响应"""

    run_id: UUID = Field(..., description="运行 ID")
    tick_no: int = Field(..., description="tick 编号")
    accepted_count: int = Field(..., description="接受的动作数量")
    rejected_count: int = Field(..., description="拒绝的动作数量")


@router.post(
    "",
    response_model=RunResponse,
    summary="创建新运行",
    description="创建一个新的 AI 模拟运行，可选择自动填充演示数据",
)
async def create_run(
    payload: RunCreateRequest,
    session: AsyncSession = Depends(get_db_session),
) -> RunResponse:
    logger.info(f"Creating new run: {payload.name}")
    repo = RunRepository(session)
    # 默认自动运行状态
    run = SimulationRun(id=str(uuid4()), name=payload.name, status="running")
    created = await repo.create(run)
    logger.info(f"Run created: id={created.id}, name={created.name}, auto-running")

    if payload.seed_demo:
        logger.debug(f"Seeding demo data for run {created.id}")
        service = SimulationService(session)
        await service.seed_demo_run(created.id)
        logger.info(f"Demo data seeded for run {created.id}")

    # 自动启动 tick 调度器
    scheduler = get_scheduler()
    logger.info(
        f"Create run completed for {created.id}, starting scheduler (running: {scheduler.is_running(created.id)})"
    )
    if not scheduler.is_running(created.id):
        from app.agent.connection_pool import get_connection_pool
        from app.agent.registry import AgentRegistry
        from app.agent.runtime import AgentRuntime
        from app.infra.db import async_engine
        from app.infra.settings import get_settings

        settings = get_settings()
        registry = AgentRegistry(settings.project_root / "agents")

        # Get connection pool and warmup agents for this run
        # IMPORTANT: Use run_id:agent_config_id as the key for connection isolation between runs
        pool = await get_connection_pool()
        agent_repo = AgentRepository(session)
        agents = await agent_repo.list_for_run(str(created.id))
        # Build pool keys with run_id prefix for multi-run isolation
        pool_keys = set()
        for a in agents:
            config_id = (a.profile or {}).get("agent_config_id")
            agent_key = config_id if config_id else a.id
            pool_keys.add(f"{created.id}:{agent_key}")
        if pool_keys:
            logger.info(f"Warming up connection pool for {len(pool_keys)} agents: {pool_keys}")
            await pool.warmup(list(pool_keys))

        # Create agent runtime with connection pool
        agent_runtime = AgentRuntime(registry=registry, connection_pool=pool)

        async def tick_callback(rid: str) -> None:
            # Use isolated tick method to avoid greenlet conflicts with anyio
            service = SimulationService.create_for_scheduler(agent_runtime)
            await service.run_tick_isolated(rid, async_engine)

        await scheduler.start_run(created.id, interval_seconds=5.0, callback=tick_callback)
        logger.info(f"Auto-scheduler started for run {created.id}")

    return RunResponse(
        id=UUID(created.id),
        name=created.name,
        status=created.status,
        was_running_before_restart=created.was_running_before_restart,
    )


@router.get(
    "",
    response_model=list[RunResponse],
    summary="列出所有运行",
    description="获取所有模拟运行的列表",
)
async def list_runs(
    session: AsyncSession = Depends(get_db_session),
) -> list[RunResponse]:
    logger.debug("Listing all runs")
    repo = RunRepository(session)
    runs = await repo.list()
    logger.debug(f"Found {len(runs)} runs")
    return [
        RunResponse(
            id=UUID(run.id),
            name=run.name,
            status=run.status,
            current_tick=run.current_tick,
            tick_minutes=run.tick_minutes,
            was_running_before_restart=run.was_running_before_restart,
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
    session: AsyncSession = Depends(get_db_session),
) -> list[RunResponse]:
    """Restore all runs that were running before server restart."""
    logger.info("Restore all runs requested")
    repo = RunRepository(session)
    runs_to_restore = await repo.list_runs_to_restore()

    if not runs_to_restore:
        logger.info("No runs to restore")
        return []

    restored: list[RunResponse] = []
    scheduler = get_scheduler()

    for run in runs_to_restore:
        try:
            # Update status to running
            updated = await repo.update_status(run, "running")

            # Start scheduler if not already running
            if not scheduler.is_running(str(run.id)):
                from app.agent.connection_pool import get_connection_pool
                from app.infra.db import async_engine
                from app.sim.service import SimulationService
                from app.agent.runtime import AgentRuntime
                from app.agent.registry import AgentRegistry
                from app.infra.settings import get_settings

                settings = get_settings()
                registry = AgentRegistry(settings.project_root / "agents")
                pool = await get_connection_pool()

                agent_repo = AgentRepository(session)
                agents = await agent_repo.list_for_run(str(run.id))
                # Build pool keys with run_id prefix for multi-run isolation
                pool_keys = set()
                for a in agents:
                    config_id = (a.profile or {}).get("agent_config_id")
                    agent_key = config_id if config_id else a.id
                    pool_keys.add(f"{run.id}:{agent_key}")

                if pool_keys:
                    logger.info(f"Warming up connection pool for run {run.id}: {pool_keys}")
                    await pool.warmup(list(pool_keys))

                agent_runtime = AgentRuntime(registry=registry, connection_pool=pool)

                async def tick_callback(rid: str) -> None:
                    service = SimulationService.create_for_scheduler(agent_runtime)
                    await service.run_tick_isolated(rid, async_engine)

                await scheduler.start_run(str(run.id), interval_seconds=5.0, callback=tick_callback)
                logger.info(f"Scheduler started for restored run {run.id}")

            # Clear the flag after successful restore
            await repo.clear_was_running_flag(updated)
            restored.append(
                RunResponse(
                    id=UUID(updated.id),
                    name=updated.name,
                    status=updated.status,
                    current_tick=updated.current_tick,
                    tick_minutes=updated.tick_minutes,
                    was_running_before_restart=False,
                )
            )
        except Exception as e:
            logger.error(f"Failed to restore run {run.id}: {e}")

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
    session: AsyncSession = Depends(get_db_session),
) -> RunResponse:
    repo = RunRepository(session)
    run = await repo.get(str(run_id))
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    updated = await repo.update_status(run, "running")

    # Start automatic tick scheduler (every 5 seconds)
    scheduler = get_scheduler()
    logger.info(
        f"Start run requested for {run_id}, scheduler running: {scheduler.is_running(str(run_id))}"
    )
    if not scheduler.is_running(str(run_id)):
        from app.agent.connection_pool import get_connection_pool
        from app.infra.db import async_engine
        from app.sim.service import SimulationService
        from app.agent.runtime import AgentRuntime
        from app.agent.registry import AgentRegistry
        from app.infra.settings import get_settings

        settings = get_settings()
        registry = AgentRegistry(settings.project_root / "agents")

        # Get connection pool and warmup agents for this run
        # IMPORTANT: Use run_id:agent_config_id as the key for connection isolation between runs
        pool = await get_connection_pool()
        agent_repo = AgentRepository(session)
        agents = await agent_repo.list_for_run(str(run_id))
        # Build pool keys with run_id prefix for multi-run isolation
        pool_keys = set()
        for a in agents:
            config_id = (a.profile or {}).get("agent_config_id")
            agent_key = config_id if config_id else a.id
            pool_keys.add(f"{run_id}:{agent_key}")

        if pool_keys:
            logger.info(f"Warming up connection pool for {len(pool_keys)} agents: {pool_keys}")
            await pool.warmup(list(pool_keys))

        # Create agent runtime with connection pool
        agent_runtime = AgentRuntime(registry=registry, connection_pool=pool)

        async def tick_callback(rid: str) -> None:
            # Use isolated tick method to avoid greenlet conflicts with anyio
            # The agent_runtime is created outside to avoid re-creating for each tick
            service = SimulationService.create_for_scheduler(agent_runtime)
            await service.run_tick_isolated(rid, async_engine)

        await scheduler.start_run(str(run_id), interval_seconds=5.0, callback=tick_callback)

    return RunResponse(
        id=run_id,
        name=updated.name,
        status=updated.status,
        was_running_before_restart=updated.was_running_before_restart,
    )


@router.post(
    "/{run_id}/pause",
    response_model=RunResponse,
    summary="暂停运行",
    description="暂停模拟运行，停止 tick 调度",
)
async def pause_run(
    run_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> RunResponse:
    repo = RunRepository(session)
    run = await repo.get(str(run_id))
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    # Stop automatic tick scheduler
    scheduler = get_scheduler()
    logger.info(f"Pause run requested for {run_id}, stopping scheduler")
    await scheduler.stop_run(str(run_id))

    # Cleanup connection pool for this run
    from app.agent.connection_pool import get_connection_pool

    pool = await get_connection_pool()
    await pool.cleanup_run(str(run_id))

    updated = await repo.update_status(run, "paused")
    return RunResponse(
        id=run_id,
        name=updated.name,
        status=updated.status,
        was_running_before_restart=updated.was_running_before_restart,
    )


@router.post(
    "/{run_id}/resume",
    response_model=RunResponse,
    summary="恢复运行",
    description="恢复已暂停的模拟运行",
)
async def resume_run(
    run_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> RunResponse:
    repo = RunRepository(session)
    run = await repo.get(str(run_id))
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    updated = await repo.update_status(run, "running")
    return RunResponse(
        id=run_id,
        name=updated.name,
        status=updated.status,
        was_running_before_restart=updated.was_running_before_restart,
    )


@router.post(
    "/{run_id}/tick",
    response_model=TickResponse,
    summary="推进 Tick",
    description="手动推进模拟运行的一个 tick，执行 agent 动作和世界更新",
)
async def advance_run_tick(
    run_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> TickResponse:
    logger.info(f"Advancing tick for run {run_id}")
    repo = RunRepository(session)
    run = await repo.get(str(run_id))
    if run is None:
        logger.warning(f"Run not found: {run_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    service = SimulationService(session)
    result = await service.run_tick(str(run_id))
    logger.info(
        f"Tick {result.tick_no} completed: "
        f"accepted={len(result.accepted)}, rejected={len(result.rejected)}"
    )
    return TickResponse(
        run_id=run_id,
        tick_no=result.tick_no,
        accepted_count=len(result.accepted),
        rejected_count=len(result.rejected),
    )


@router.get(
    "/{run_id}",
    summary="获取运行详情",
    description="获取指定模拟运行的详细状态信息",
)
async def get_run(
    run_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, object]:
    repo = RunRepository(session)
    run = await repo.get(str(run_id))
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return {
        "id": run.id,
        "name": run.name,
        "status": run.status,
        "current_tick": run.current_tick,
        "tick_minutes": run.tick_minutes,
    }


@router.get(
    "/{run_id}/timeline",
    summary="获取时间线",
    description="获取模拟运行的完整事件时间线",
)
async def get_timeline(
    run_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, object]:
    run_repo = RunRepository(session)
    run = await run_repo.get(str(run_id))
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    event_repo = EventRepository(session)
    events = await event_repo.list_for_run(str(run_id))
    return {
        "run_id": str(run_id),
        "events": [
            {
                "id": event.id,
                "tick_no": event.tick_no,
                "event_type": event.event_type,
                "importance": event.importance,
                "payload": event.payload,
            }
            for event in events
        ],
    }


@router.get(
    "/{run_id}/director/observation",
    summary="获取导演观察",
    description="获取只读导演观察结果，包括 Truman 怀疑度和世界连续性风险",
)
async def get_director_observation(
    run_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, object]:
    repo = RunRepository(session)
    run = await repo.get(str(run_id))
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    service = SimulationService(session)
    assessment = await service.observe_run(str(run_id))

    return {
        "run_id": str(run_id),
        "current_tick": assessment.current_tick,
        "truman_agent_id": assessment.truman_agent_id,
        "truman_suspicion_score": assessment.truman_suspicion_score,
        "suspicion_level": assessment.suspicion_level,
        "continuity_risk": assessment.continuity_risk,
        "focus_agent_ids": assessment.focus_agent_ids,
        "notes": assessment.notes,
    }


@router.get(
    "/{run_id}/world",
    summary="获取世界快照",
    description="获取模拟世界的实时快照，包括地点、agent 分布和最近事件",
)
async def get_world_snapshot(
    run_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, object]:
    run_repo = RunRepository(session)
    run = await run_repo.get(str(run_id))
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    agent_repo = AgentRepository(session)
    location_repo = LocationRepository(session)
    event_repo = EventRepository(session)

    agents = await agent_repo.list_for_run(str(run_id))
    locations = await location_repo.list_for_run(str(run_id))
    events = await event_repo.list_for_run(str(run_id), limit=12)

    agent_summaries = {
        agent.id: {
            "id": agent.id,
            "name": agent.name,
            "occupation": agent.occupation,
            "current_goal": agent.current_goal,
            "current_location_id": agent.current_location_id,
            "config_id": (agent.profile or {}).get("agent_config_id"),
        }
        for agent in agents
    }

    locations_payload = []
    for location in locations:
        occupants = [
            agent_summaries[agent.id]
            for agent in agents
            if agent.current_location_id == location.id
        ]
        locations_payload.append(
            {
                "id": location.id,
                "name": location.name,
                "location_type": location.location_type,
                "x": location.x,
                "y": location.y,
                "capacity": location.capacity,
                "occupants": occupants,
            }
        )

    # Calculate world time context
    world_time = get_run_world_time(run)
    weekday = world_time.weekday()
    weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    weekday_names_cn = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    
    hour = world_time.hour
    if hour < 6:
        time_period = "night"
        time_period_cn = "深夜"
    elif hour < 9:
        time_period = "morning"
        time_period_cn = "早晨"
    elif hour < 12:
        time_period = "late_morning"
        time_period_cn = "上午"
    elif hour < 14:
        time_period = "noon"
        time_period_cn = "中午"
    elif hour < 18:
        time_period = "afternoon"
        time_period_cn = "下午"
    elif hour < 22:
        time_period = "evening"
        time_period_cn = "傍晚"
    else:
        time_period = "night"
        time_period_cn = "夜晚"

    world_clock = {
        "iso": world_time.isoformat(),
        "date": world_time.strftime("%Y-%m-%d"),
        "time": world_time.strftime("%H:%M"),
        "year": world_time.year,
        "month": world_time.month,
        "day": world_time.day,
        "hour": hour,
        "minute": world_time.minute,
        "weekday": weekday,
        "weekday_name": weekday_names[weekday],
        "weekday_name_cn": weekday_names_cn[weekday],
        "is_weekend": weekday >= 5,
        "time_period": time_period,
        "time_period_cn": time_period_cn,
    }

    # Build agent and location name maps for event enrichment
    agent_name_map = {agent.id: agent.name for agent in agents}
    location_name_map = {location.id: location.name for location in locations}

    return {
        "run": {
            "id": run.id,
            "name": run.name,
            "status": run.status,
            "current_tick": run.current_tick,
            "tick_minutes": run.tick_minutes,
        },
        "world_clock": world_clock,
        "locations": locations_payload,
        "recent_events": [
            {
                "id": event.id,
                "tick_no": event.tick_no,
                "event_type": event.event_type,
                "location_id": event.location_id,
                "actor_agent_id": event.actor_agent_id,
                "target_agent_id": event.target_agent_id,
                "actor_name": agent_name_map.get(event.actor_agent_id) if event.actor_agent_id else None,
                "target_name": agent_name_map.get(event.target_agent_id) if event.target_agent_id else None,
                "location_name": location_name_map.get(event.location_id) if event.location_id else None,
                "payload": event.payload,
            }
            for event in events
            if event.visibility == "public"
        ],
    }


@router.post(
    "/{run_id}/director/events",
    summary="导演事件注入",
    description="""
**导演系统 - 注入事件**

作为导演向模拟世界注入事件，影响 agent 行为和世界走向。

支持的事件类型：
- `activity`: 举办活动（如"咖啡馆派对"）
- `shutdown`: 临时关闭地点
- `broadcast`: 全服广播消息
- `weather_change`: 天气变化

注意：导演系统仅限于简单世界事件，不允许直接修改 agent 属性或关系。
    """,
)
async def inject_director_event(
    run_id: UUID,
    payload: DirectorEventRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    repo = RunRepository(session)
    run = await repo.get(str(run_id))
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    service = SimulationService(session)
    await service.inject_director_event(
        run_id=str(run_id),
        event_type=payload.event_type,
        payload=payload.payload,
        location_id=payload.location_id,
        importance=payload.importance,
    )
    return {"run_id": str(run_id), "status": "queued"}


@router.delete(
    "/{run_id}",
    summary="删除运行",
    description="""
**删除模拟运行**

删除指定运行及其所有关联数据（agents、locations、events、memories、relationships）。

这是一个破坏性操作，无法撤销。
    """,
)
async def delete_run(
    run_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """Delete a run and all its associated data."""
    logger.info(f"Deleting run: {run_id}")

    # Stop scheduler if running
    scheduler = get_scheduler()
    await scheduler.stop_run(str(run_id))

    # Cleanup connection pool for this run
    from app.agent.connection_pool import get_connection_pool

    pool = await get_connection_pool()
    await pool.cleanup_run(str(run_id))

    repo = RunRepository(session)
    run = await repo.get(str(run_id))
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    # Delete related data in correct order (respecting foreign key constraints)
    # Order: relationships -> memories -> events -> agents -> locations -> run
    from sqlalchemy import delete
    from app.store.models import Agent, Event, Location, Memory, Relationship

    run_id_str = str(run_id)

    # Delete relationships (references agents)
    await session.execute(delete(Relationship).where(Relationship.run_id == run_id_str))

    # Delete memories (references agents)
    await session.execute(delete(Memory).where(Memory.run_id == run_id_str))

    # Delete events (references agents, locations)
    await session.execute(delete(Event).where(Event.run_id == run_id_str))

    # Delete agents (references locations)
    await session.execute(delete(Agent).where(Agent.run_id == run_id_str))

    # Delete locations
    await session.execute(delete(Location).where(Location.run_id == run_id_str))

    # Finally delete the run
    await repo.delete(run)
    logger.info(f"Run deleted: {run_id}")

    return {"run_id": str(run_id), "status": "deleted"}
