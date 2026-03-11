import asyncio
from datetime import datetime
import json
from uuid import UUID, uuid4
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.simulation import (
    DirectorObservationResponse,
    DirectorMemoriesResponse,
    DirectorMemoryResponse,
    RunDetailResponse,
    StatusResponse,
    TimelineEventResponse,
    TimelineResponse,
    TimelineRunInfo,
    WorldClockResponse,
    WorldDailyStatsResponse,
    WorldDirectorStatsResponse,
    WorldEventResponse,
    WorldEventsResponse,
    WorldHealthMetricsConfig,
    WorldLocationResponse,
    WorldSnapshotResponse,
    WorldSnapshotRunResponse,
    AgentSummaryResponse,
)
from app.director.service import DirectorEventService
from app.infra.db import get_db_session
from app.infra.logging import get_logger
from app.scenario.factory import create_scenario
from app.scenario.truman_world.rules import load_world_config
from app.scenario.truman_world.types import get_agent_config_id
from app.sim.context import get_run_world_time
from app.sim.run_lifecycle import ensure_run_started, pause_run_execution
from app.sim.scheduler import get_scheduler
from app.sim.service import SimulationService
from app.store.models import Agent, Event, Location, SimulationRun
from app.store.repositories import (
    AgentRepository,
    DirectorMemoryRepository,
    EventRepository,
    LlmCallRepository,
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
    scenario_type: Literal["truman_world", "open_world"] = Field(
        default="truman_world",
        description="运行场景类型",
        examples=["truman_world", "open_world"],
    )
    seed_demo: bool = Field(
        default=True,
        description="是否自动填充演示数据（agent、地点等）",
        examples=[True],
    )
    tick_minutes: int = Field(
        default=5,
        ge=1,
        le=60,
        description="每个 tick 代表的分钟数",
        examples=[5],
    )


class RunResponse(BaseModel):
    """模拟运行响应"""

    id: UUID = Field(..., description="运行 ID")
    name: str = Field(..., description="运行名称")
    status: str = Field(..., description="运行状态", examples=["running", "paused", "stopped"])
    scenario_type: str = Field(..., description="运行场景类型", examples=["truman_world"])
    current_tick: int | None = Field(None, description="当前 tick 数")
    tick_minutes: int | None = Field(None, description="每个 tick 代表的分钟数")
    was_running_before_restart: bool = Field(
        False, description="服务重启前是否在运行中（用于一键恢复）"
    )
    agent_count: int = Field(0, description="本次运行的 agent 数量")
    location_count: int = Field(0, description="本次运行的地点数量")
    event_count: int = Field(0, description="本次运行产生的事件总数")
    started_at: datetime | None = Field(None, description="最近一次启动时间（UTC ISO8601）")
    elapsed_seconds: int = Field(0, description="每次暂停前累计运行秒数")


class DirectorEventRequest(BaseModel):
    """导演事件注入请求"""

    event_type: Literal["activity", "shutdown", "broadcast", "weather_change"] = Field(
        ...,
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


def build_run_response(run: SimulationRun) -> RunResponse:
    return RunResponse(
        id=UUID(run.id),
        name=run.name,
        status=run.status,
        scenario_type=run.scenario_type,
        current_tick=run.current_tick,
        tick_minutes=run.tick_minutes,
        was_running_before_restart=run.was_running_before_restart,
        started_at=run.started_at,
        elapsed_seconds=run.elapsed_seconds or 0,
    )


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
    run = SimulationRun(
        id=str(uuid4()),
        name=payload.name,
        status="running",
        scenario_type=payload.scenario_type,
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

    # 批量聚合计数，避免 N+1 查询
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
        RunResponse(
            id=UUID(run.id),
            name=run.name,
            status=run.status,
            scenario_type=run.scenario_type,
            current_tick=run.current_tick,
            tick_minutes=run.tick_minutes,
            was_running_before_restart=run.was_running_before_restart,
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

    for run in runs_to_restore:
        try:
            updated = await ensure_run_started(session, run)
            await repo.clear_was_running_flag(updated)
            refreshed = await repo.get(updated.id)
            if refreshed is not None:
                restored.append(build_run_response(refreshed))
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
    updated = await ensure_run_started(session, run)
    # Clear the restore flag now that the run is actively started
    await repo.clear_was_running_flag(updated)
    refreshed = await repo.get(updated.id)
    return build_run_response(refreshed or updated)


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
    session: AsyncSession = Depends(get_db_session),
) -> RunResponse:
    repo = RunRepository(session)
    run = await repo.get(str(run_id))
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    updated = await ensure_run_started(session, run)
    # Clear the restore flag now that the run is actively resumed
    await repo.clear_was_running_flag(updated)
    refreshed = await repo.get(updated.id)
    return build_run_response(refreshed or updated)


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
    response_model=RunDetailResponse,
    summary="获取运行详情",
    description="获取指定模拟运行的详细状态信息",
)
async def get_run(
    run_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> RunDetailResponse:
    repo = RunRepository(session)
    run = await repo.get(str(run_id))
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return RunDetailResponse(
        id=run.id,
        name=run.name,
        status=run.status,
        scenario_type=run.scenario_type,
        current_tick=run.current_tick,
        tick_minutes=run.tick_minutes,
    )


@router.get(
    "/{run_id}/timeline",
    response_model=TimelineResponse,
    summary="获取时间线",
    description="获取模拟运行的完整事件时间线，支持按 tick 范围、模拟世界时间范围、事件类型、角色等多维过滤。支持正序/倒序排列。",
)
async def get_timeline(
    run_id: UUID,
    tick_from: int | None = None,
    tick_to: int | None = None,
    world_datetime_from: str | None = None,  # YYYY-MM-DDTHH:MM 格式，模拟世界日期时间起始
    world_datetime_to: str | None = None,  # YYYY-MM-DDTHH:MM 格式，模拟世界日期时间结束
    event_type: str | None = None,
    agent_id: str | None = None,
    limit: int = 2000,
    offset: int = 0,
    order_desc: bool = False,  # 是否按 tick 倒序排列（最新事件在前）
    session: AsyncSession = Depends(get_db_session),
) -> TimelineResponse:
    from datetime import timedelta
    from app.sim.context import DEFAULT_WORLD_START_TIME
    from datetime import UTC

    run_repo = RunRepository(session)
    run = await run_repo.get(str(run_id))
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    agent_repo = AgentRepository(session)
    location_repo = LocationRepository(session)
    event_repo = EventRepository(session)

    agents, locations = await asyncio.gather(
        agent_repo.list_for_run(str(run_id)),
        location_repo.list_for_run(str(run_id)),
    )
    agent_name_map = {agent.id: agent.name for agent in agents}
    location_name_map = {location.id: location.name for location in locations}
    metadata = run.metadata_json or {}
    raw_start = metadata.get("world_start_time")
    if isinstance(raw_start, str):
        try:
            world_start = datetime.fromisoformat(raw_start)
        except ValueError:
            world_start = DEFAULT_WORLD_START_TIME
    else:
        world_start = DEFAULT_WORLD_START_TIME
    if world_start.tzinfo is None:
        world_start = world_start.replace(tzinfo=UTC)

    tick_minutes = run.tick_minutes or 5

    # 将模拟世界日期时间转化为精确的 tick 范围
    # 公式：tick_no = floor((target_datetime - world_start).total_seconds / 60 / tick_minutes)
    resolved_tick_from = tick_from
    resolved_tick_to = tick_to

    def parse_world_datetime(raw: str) -> datetime | None:
        """解析 YYYY-MM-DDTHH:MM 或 YYYY-MM-DD HH:MM 为 datetime（UTC 时区）。"""
        for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S"):
            try:
                dt = datetime.strptime(raw.strip(), fmt)
                return dt.replace(tzinfo=UTC)
            except ValueError:
                continue
        return None

    if world_datetime_from:
        dt_from = parse_world_datetime(world_datetime_from)
        if dt_from is not None:
            elapsed = (dt_from - world_start).total_seconds() / 60
            candidate = max(0, int(elapsed // tick_minutes))
            if resolved_tick_from is None:
                resolved_tick_from = candidate
            else:
                resolved_tick_from = min(resolved_tick_from, candidate)

    if world_datetime_to:
        dt_to = parse_world_datetime(world_datetime_to)
        if dt_to is not None:
            elapsed = (dt_to - world_start).total_seconds() / 60
            candidate = max(0, int(elapsed // tick_minutes))
            if resolved_tick_to is None:
                resolved_tick_to = candidate
            else:
                resolved_tick_to = max(resolved_tick_to, candidate)

    # 如果传入的是 agent 名称而非 ID，先做名称 -> ID 的映射
    resolved_agent_id = agent_id
    if agent_id and agent_id not in agent_name_map:
        for a in agents:
            if a.name.lower() == agent_id.lower():
                resolved_agent_id = a.id
                break

    events, total = await event_repo.list_timeline_events(
        run_id=str(run_id),
        tick_from=resolved_tick_from,
        tick_to=resolved_tick_to,
        event_type=event_type,
        actor_agent_id=resolved_agent_id,
        limit=limit,
        offset=offset,
        order_desc=order_desc,
    )

    def enrich_payload(event) -> dict:
        """Inject actor_name / target_name / location_name into payload."""
        payload = dict(event.payload or {})
        if event.actor_agent_id and "actor_name" not in payload:
            payload["actor_name"] = agent_name_map.get(event.actor_agent_id, event.actor_agent_id)
        if event.target_agent_id and "target_name" not in payload:
            payload["target_name"] = agent_name_map.get(
                event.target_agent_id, event.target_agent_id
            )
        if event.location_id and "location_name" not in payload:
            payload["location_name"] = location_name_map.get(event.location_id, event.location_id)
        return payload

    def tick_to_world_time(tick_no: int) -> tuple[str, str]:
        """Returns (HH:MM, YYYY-MM-DD) for the given tick."""
        dt = world_start + timedelta(minutes=tick_no * tick_minutes)
        return dt.strftime("%H:%M"), dt.strftime("%Y-%m-%d")

    current_world_time = get_run_world_time(run)

    return TimelineResponse(
        run_id=str(run_id),
        total=total,
        filtered=len(events),
        run_info=TimelineRunInfo(
            current_tick=run.current_tick or 0,
            tick_minutes=tick_minutes,
            world_start_iso=world_start.isoformat(),
            current_world_time_iso=current_world_time.isoformat(),
        ),
        events=[
            TimelineEventResponse(
                id=event.id,
                tick_no=event.tick_no,
                event_type=event.event_type,
                importance=event.importance,
                payload=enrich_payload(event),
                world_time=tick_to_world_time(event.tick_no)[0],
                world_date=tick_to_world_time(event.tick_no)[1],
            )
            for event in events
        ],
    )


@router.get(
    "/{run_id}/events",
    response_model=WorldEventsResponse,
    summary="获取全量事件",
    description="获取 run 的全量历史事件，包含富字段（actor_name, location_name 等），支持按事件类型过滤和增量查询（since_tick）",
)
async def get_run_events(
    run_id: UUID,
    event_type: str | None = None,
    limit: int = 500,
    since_tick: int | None = None,
    session: AsyncSession = Depends(get_db_session),
) -> WorldEventsResponse:
    run_repo = RunRepository(session)
    run = await run_repo.get(str(run_id))
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    agent_repo = AgentRepository(session)
    location_repo = LocationRepository(session)
    event_repo = EventRepository(session)

    agents, locations, events = await asyncio.gather(
        agent_repo.list_for_run(str(run_id)),
        location_repo.list_for_run(str(run_id)),
        event_repo.list_for_run(str(run_id), limit=limit, since_tick=since_tick),
    )

    agent_name_map = {agent.id: agent.name for agent in agents}
    location_name_map = {location.id: location.name for location in locations}

    # Apply event_type filter if provided
    if event_type:
        filter_types: set[str] = set()
        if event_type == "social":
            filter_types = {"talk"}
        elif event_type == "movement":
            filter_types = {"move"}
        elif event_type == "activity":
            filter_types = {"work", "rest"}
        else:
            filter_types = {event_type}
        events = [e for e in events if e.event_type in filter_types]

    result_events = [
        WorldEventResponse(
            id=event.id,
            tick_no=event.tick_no,
            event_type=event.event_type,
            location_id=event.location_id,
            actor_agent_id=event.actor_agent_id,
            target_agent_id=event.target_agent_id,
            actor_name=agent_name_map.get(event.actor_agent_id) if event.actor_agent_id else None,
            target_name=agent_name_map.get(event.target_agent_id)
            if event.target_agent_id
            else None,
            location_name=location_name_map.get(event.location_id) if event.location_id else None,
            payload=event.payload or {},
        )
        for event in events
    ]

    # 计算返回事件中的最大 tick，供增量查询使用
    latest_tick = max((e.tick_no for e in events), default=0)

    return WorldEventsResponse(
        run_id=str(run_id),
        events=result_events,
        total=len(result_events),
        latest_tick=latest_tick,
    )


@router.get(
    "/{run_id}/director/observation",
    response_model=DirectorObservationResponse,
    summary="获取导演观察",
    description="获取只读导演观察结果，包括 Truman 怀疑度和世界连续性风险",
)
async def get_director_observation(
    run_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> DirectorObservationResponse:
    repo = RunRepository(session)
    run = await repo.get(str(run_id))
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    service = SimulationService(session)
    assessment = await service.observe_run(str(run_id))

    return DirectorObservationResponse(
        run_id=str(run_id),
        current_tick=assessment.current_tick,
        truman_agent_id=assessment.truman_agent_id,
        truman_suspicion_score=assessment.truman_suspicion_score,
        suspicion_level=assessment.suspicion_level,
        continuity_risk=assessment.continuity_risk,
        focus_agent_ids=assessment.focus_agent_ids,
        notes=assessment.notes,
    )


@router.get(
    "/{run_id}/director/memories",
    response_model=DirectorMemoriesResponse,
    summary="获取导演干预明细",
    description="获取导演干预计划明细，支持前端查看全部、未执行和已执行记录。",
)
async def get_director_memories(
    run_id: UUID,
    limit: int = 50,
    session: AsyncSession = Depends(get_db_session),
) -> DirectorMemoriesResponse:
    run_repo = RunRepository(session)
    run = await run_repo.get(str(run_id))
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    agent_repo = AgentRepository(session)
    location_repo = LocationRepository(session)
    director_memory_repo = DirectorMemoryRepository(session)

    agents = await agent_repo.list_for_run(str(run_id))
    locations = await location_repo.list_for_run(str(run_id))
    memories = await director_memory_repo.list_for_run(str(run_id), limit=limit)

    agent_name_map = {agent.id: agent.name for agent in agents}
    location_name_map = {location.id: location.name for location in locations}
    manual_goals = {"gather", "activity", "shutdown", "weather_change"}

    def serialize_memory(memory) -> DirectorMemoryResponse:
        target_cast_ids = json.loads(memory.target_cast_ids) if memory.target_cast_ids else []
        location_hint = None
        if memory.metadata_json:
            location_hint = memory.metadata_json.get("location_hint")
        if memory.was_executed:
            delivery_status = "consumed"
        elif memory.scene_goal in manual_goals and run.current_tick > memory.tick_no + 5:
            delivery_status = "expired"
        else:
            delivery_status = "queued"

        return DirectorMemoryResponse(
            id=memory.id,
            tick_no=memory.tick_no,
            scene_goal=memory.scene_goal,
            priority=memory.priority,
            urgency=memory.urgency,
            message_hint=memory.message_hint,
            target_agent_id=memory.target_agent_id,
            target_agent_name=(
                agent_name_map.get(memory.target_agent_id) if memory.target_agent_id else None
            ),
            target_cast_ids=target_cast_ids,
            target_cast_names=[
                agent_name_map.get(agent_id, agent_id) for agent_id in target_cast_ids
            ],
            location_hint=location_hint,
            location_name=location_name_map.get(location_hint) if location_hint else None,
            reason=memory.reason,
            was_executed=memory.was_executed,
            delivery_status=delivery_status,
            effectiveness_score=memory.effectiveness_score,
            trigger_suspicion_score=memory.trigger_suspicion_score,
            trigger_continuity_risk=memory.trigger_continuity_risk,
            cooldown_ticks=memory.cooldown_ticks,
            cooldown_until_tick=memory.cooldown_until_tick,
            created_at=memory.created_at,
        )

    return DirectorMemoriesResponse(
        run_id=str(run_id),
        memories=[serialize_memory(memory) for memory in memories],
        total=len(memories),
    )


def _build_health_metrics_config() -> WorldHealthMetricsConfig:
    """Load health metrics evaluation baselines from world_config.yml."""
    try:
        world_cfg = load_world_config()
        cfg = world_cfg.get("health_metrics", {})
        cont = cfg.get("continuity", {})
        soc = cfg.get("social", {})
        heat = world_cfg.get("location_heat", {})
        thresholds = heat.get("thresholds", {})
        ui = world_cfg.get("ui_config", {})
        ui_loc = ui.get("location_detail", {})
        ui_intel = ui.get("intelligence_stream", {})
        ui_dir = ui.get("director_panel", {})
        return WorldHealthMetricsConfig(
            continuity_penalty_factor=cont.get("penalty_factor", 200.0),
            continuity_warning_threshold=cont.get("warning_threshold", 0.2),
            continuity_trend_down_threshold=cont.get("trend_down_threshold", 0.15),
            continuity_trend_stable_threshold=cont.get("trend_stable_threshold", 0.05),
            social_baseline_talks_per_person_per_day=soc.get(
                "baseline_talks_per_person_per_day", 20.0
            ),
            social_trend_up_threshold=soc.get("trend_up_threshold", 10.0),
            social_trend_stable_threshold=soc.get("trend_stable_threshold", 3.0),
            heat_normalization_baseline=heat.get("normalization_baseline", 30.0),
            heat_threshold_very_active=thresholds.get("very_active", 0.7),
            heat_threshold_active=thresholds.get("active", 0.4),
            heat_threshold_mild=thresholds.get("mild", 0.15),
            heat_glow_threshold=heat.get("glow_threshold", 0.1),
            ui_location_detail_max_events=ui_loc.get("max_events_display", 50),
            ui_intelligence_stream_max_events=ui_intel.get("max_events_load", 500),
            ui_intelligence_stream_poll_interval=ui_intel.get("poll_interval_ms", 5000),
            ui_director_panel_max_memories=ui_dir.get("max_memories_load", 100),
        )
    except Exception:
        return WorldHealthMetricsConfig()


@router.get(
    "/{run_id}/world",
    response_model=WorldSnapshotResponse,
    summary="获取世界快照",
    description="获取模拟世界的实时快照，包括地点、agent 分布和最近事件",
)
async def get_world_snapshot(
    run_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> WorldSnapshotResponse:
    run_repo = RunRepository(session)
    run = await run_repo.get(str(run_id))
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    agent_repo = AgentRepository(session)
    location_repo = LocationRepository(session)
    event_repo = EventRepository(session)
    director_memory_repo = DirectorMemoryRepository(session)
    llm_call_repo = LlmCallRepository(session)

    agents = await agent_repo.list_for_run(str(run_id))
    locations = await location_repo.list_for_run(str(run_id))
    events = await event_repo.list_for_run(str(run_id), limit=120)
    director_total = await director_memory_repo.count_for_run(str(run_id))
    director_executed = await director_memory_repo.count_executed_for_run(str(run_id))

    agent_summaries = {
        agent.id: AgentSummaryResponse(
            id=agent.id,
            name=agent.name,
            occupation=agent.occupation,
            current_goal=agent.current_goal,
            current_location_id=agent.current_location_id,
            config_id=get_agent_config_id(agent.profile),
        )
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
    if hour < 5:
        time_period = "night"
        time_period_cn = "深夜"
    elif hour < 7:
        time_period = "dawn"
        time_period_cn = "黎明"
    elif hour < 12:
        time_period = "morning"
        time_period_cn = "上午"
    elif hour < 14:
        time_period = "noon"
        time_period_cn = "中午"
    elif hour < 18:
        time_period = "afternoon"
        time_period_cn = "下午"
    elif hour < 21:
        time_period = "evening"
        time_period_cn = "傍晚"
    else:
        time_period = "night"
        time_period_cn = "夜晚"

    world_clock = WorldClockResponse(
        iso=world_time.isoformat(),
        date=world_time.strftime("%Y-%m-%d"),
        time=world_time.strftime("%H:%M"),
        year=world_time.year,
        month=world_time.month,
        day=world_time.day,
        hour=hour,
        minute=world_time.minute,
        weekday=weekday,
        weekday_name=weekday_names[weekday],
        weekday_name_cn=weekday_names_cn[weekday],
        is_weekend=weekday >= 5,
        time_period=time_period,
        time_period_cn=time_period_cn,
    )

    # Build agent and location name maps for event enrichment
    agent_name_map = {agent.id: agent.name for agent in agents}
    location_name_map = {location.id: location.name for location in locations}

    # Get all-time event statistics (not just today)
    all_time_event_counts = await event_repo.count_events_by_type(
        str(run_id),
        tick_from=None,  # No tick_from limit - get all events from the beginning
        tick_to=None,  # No tick_to limit - get all events up to now
        event_types=["talk", "move", "move_rejected", "talk_rejected"],
    )
    # Get all-time token consumption totals
    token_totals = await llm_call_repo.get_token_totals(str(run_id))

    return WorldSnapshotResponse(
        run=WorldSnapshotRunResponse(
            id=run.id,
            name=run.name,
            status=run.status,
            scenario_type=run.scenario_type,
            current_tick=run.current_tick,
            tick_minutes=run.tick_minutes,
            started_at=run.started_at,
            elapsed_seconds=run.elapsed_seconds or 0,
        ),
        world_clock=world_clock,
        locations=[
            WorldLocationResponse(**location_payload) for location_payload in locations_payload
        ],
        recent_events=[
            WorldEventResponse(
                id=event.id,
                tick_no=event.tick_no,
                event_type=event.event_type,
                location_id=event.location_id,
                actor_agent_id=event.actor_agent_id,
                target_agent_id=event.target_agent_id,
                actor_name=agent_name_map.get(event.actor_agent_id)
                if event.actor_agent_id
                else None,
                target_name=agent_name_map.get(event.target_agent_id)
                if event.target_agent_id
                else None,
                location_name=location_name_map.get(event.location_id)
                if event.location_id
                else None,
                payload=event.payload or {},
            )
            for event in events
            if event.visibility == "public"
        ],
        director_stats=WorldDirectorStatsResponse(
            total=director_total,
            executed=director_executed,
            execution_rate=(
                round((director_executed / director_total) * 100) if director_total > 0 else 0
            ),
        ),
        daily_stats=WorldDailyStatsResponse(
            talk_count=all_time_event_counts.get("talk", 0),
            move_count=all_time_event_counts.get("move", 0),
            rejection_count=all_time_event_counts.get("move_rejected", 0)
            + all_time_event_counts.get("talk_rejected", 0),
            total_input_tokens=token_totals.get("input_tokens", 0),
            total_output_tokens=token_totals.get("output_tokens", 0),
            total_cache_read_tokens=token_totals.get("cache_read_tokens", 0),
            total_cache_creation_tokens=token_totals.get("cache_creation_tokens", 0),
        ),
        health_metrics_config=_build_health_metrics_config(),
    )


@router.post(
    "/{run_id}/director/events",
    response_model=StatusResponse,
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
) -> StatusResponse:
    repo = RunRepository(session)
    run = await repo.get(str(run_id))
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    try:
        await DirectorEventService(session).inject_event(
            run_id=str(run_id),
            event_type=payload.event_type,
            payload=payload.payload,
            location_id=payload.location_id,
            importance=payload.importance,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return StatusResponse(run_id=str(run_id), status="queued")


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
    session: AsyncSession = Depends(get_db_session),
) -> StatusResponse:
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
    # Order: relationships -> memories -> director_memories -> events -> llm_calls -> agents -> locations -> run
    from sqlalchemy import delete
    from app.store.models import (
        Agent,
        DirectorMemory,
        Event,
        Location,
        Memory,
        Relationship,
        LlmCall,
    )

    run_id_str = str(run_id)

    # Delete relationships (references agents)
    await session.execute(delete(Relationship).where(Relationship.run_id == run_id_str))

    # Delete memories (references agents)
    await session.execute(delete(Memory).where(Memory.run_id == run_id_str))

    # Delete director memories
    await session.execute(delete(DirectorMemory).where(DirectorMemory.run_id == run_id_str))

    # Delete events (references agents, locations)
    await session.execute(delete(Event).where(Event.run_id == run_id_str))

    # Delete llm_calls (references agents)
    await session.execute(delete(LlmCall).where(LlmCall.run_id == run_id_str))

    # Delete agents (references locations)
    await session.execute(delete(Agent).where(Agent.run_id == run_id_str))

    # Delete locations
    await session.execute(delete(Location).where(Location.run_id == run_id_str))

    # Finally delete the run
    await repo.delete(run)
    logger.info(f"Run deleted: {run_id}")

    return StatusResponse(run_id=str(run_id), status="deleted")
