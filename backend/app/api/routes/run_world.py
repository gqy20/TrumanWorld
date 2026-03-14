import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.runs import build_run_payload, get_required_run
from app.api.schemas.simulation import (
    COMMON_RESPONSES,
    AgentSummaryResponse,
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
    WorldPulseResponse,
    WorldSnapshotResponse,
    WorldSnapshotRunResponse,
)
from app.infra.db import get_db_session
from app.infra.logging import get_logger
from app.scenario.truman_world.rules import load_world_config
from app.scenario.truman_world.types import get_agent_config_id
from app.sim.context import DEFAULT_WORLD_START_TIME, get_run_world_time
from app.store.repositories import (
    AgentRepository,
    DirectorMemoryRepository,
    EventRepository,
    LlmCallRepository,
    LocationRepository,
)

router = APIRouter()
logger = get_logger(__name__)

DEFAULT_TIMELINE_LIMIT = 500
WORLD_RECENT_EVENT_LIMIT = 60


def build_name_maps(agents, locations) -> tuple[dict[str, str], dict[str, str]]:
    return (
        {agent.id: agent.name for agent in agents},
        {location.id: location.name for location in locations},
    )


def build_occupants_by_location(agents) -> dict[str, list]:
    occupants_by_location: dict[str, list] = {}
    for agent in agents:
        if not agent.current_location_id:
            continue
        occupants_by_location.setdefault(agent.current_location_id, []).append(agent)
    return occupants_by_location


def enrich_event_payload(
    event, agent_name_map: dict[str, str], location_name_map: dict[str, str]
) -> dict:
    """Ensure all name fields are present in event payload.

    This is the single authoritative layer that guarantees readable names in
    every event payload sent to the frontend.  action_resolver may optionally
    inline names at write-time (faster), but this function always fills any
    gaps so historical data and all event types are handled uniformly.
    """
    payload = dict(event.payload or {})
    # Actor / target names
    if event.actor_agent_id and "actor_name" not in payload:
        payload["actor_name"] = agent_name_map.get(event.actor_agent_id, event.actor_agent_id)
    if event.target_agent_id and "target_name" not in payload:
        payload["target_name"] = agent_name_map.get(event.target_agent_id, event.target_agent_id)
    # Current/origin location name
    if event.location_id and "location_name" not in payload:
        payload["location_name"] = location_name_map.get(event.location_id, event.location_id)
    # Destination location name (move events)
    to_loc_id = payload.get("to_location_id")
    if to_loc_id and "to_location_name" not in payload:
        payload["to_location_name"] = location_name_map.get(str(to_loc_id), str(to_loc_id))
    # Origin location name (move events — for "A → B" display)
    from_loc_id = payload.get("from_location_id")
    if from_loc_id and "from_location_name" not in payload:
        payload["from_location_name"] = location_name_map.get(str(from_loc_id), str(from_loc_id))
    return payload


def build_world_event_response(
    event, agent_name_map: dict[str, str], location_name_map: dict[str, str]
) -> WorldEventResponse:
    return WorldEventResponse(
        id=event.id,
        tick_no=event.tick_no,
        event_type=event.event_type,
        location_id=event.location_id,
        actor_agent_id=event.actor_agent_id,
        target_agent_id=event.target_agent_id,
        actor_name=agent_name_map.get(event.actor_agent_id) if event.actor_agent_id else None,
        target_name=agent_name_map.get(event.target_agent_id) if event.target_agent_id else None,
        location_name=location_name_map.get(event.location_id) if event.location_id else None,
        payload=event.payload or {},
    )


def resolve_world_start(run) -> datetime:
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
    return world_start


def parse_world_datetime(raw: str) -> datetime | None:
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.strptime(raw.strip(), fmt)
            return dt.replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def resolve_tick_bound(
    world_datetime: str | None,
    world_start: datetime,
    tick_minutes: int,
    current_value: int | None,
    *,
    prefer_min: bool,
) -> int | None:
    if not world_datetime:
        return current_value

    parsed = parse_world_datetime(world_datetime)
    if parsed is None:
        return current_value

    candidate = max(0, int(((parsed - world_start).total_seconds() / 60) // tick_minutes))
    if current_value is None:
        return candidate
    return min(current_value, candidate) if prefer_min else max(current_value, candidate)


def tick_to_world_time(tick_no: int, world_start: datetime, tick_minutes: int) -> tuple[str, str]:
    dt = world_start + timedelta(minutes=tick_no * tick_minutes)
    return dt.strftime("%H:%M"), dt.strftime("%Y-%m-%d")


def build_timeline_event_response(
    event,
    agent_name_map: dict[str, str],
    location_name_map: dict[str, str],
    world_start: datetime,
    tick_minutes: int,
) -> TimelineEventResponse:
    world_time, world_date = tick_to_world_time(event.tick_no, world_start, tick_minutes)
    return TimelineEventResponse(
        id=event.id,
        tick_no=event.tick_no,
        event_type=event.event_type,
        importance=event.importance,
        payload=enrich_event_payload(event, agent_name_map, location_name_map),
        world_time=world_time,
        world_date=world_date,
    )


def build_world_clock(world_time: datetime) -> WorldClockResponse:
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

    return WorldClockResponse(
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


def build_run_snapshot(run) -> WorldSnapshotRunResponse:
    return WorldSnapshotRunResponse(**build_run_payload(run))


def _build_health_metrics_config() -> WorldHealthMetricsConfig:
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
    "/{run_id}/timeline",
    response_model=TimelineResponse,
    summary="获取时间线",
    description="获取模拟运行的完整事件时间线，支持按 tick 范围、模拟世界时间范围、事件类型、角色等多维过滤。支持正序/倒序排列。",
    responses={
        **COMMON_RESPONSES,
        200: {"description": "时间线事件列表", "model": TimelineResponse},
    },
)
async def get_timeline(
    run_id: UUID,
    tick_from: int | None = None,
    tick_to: int | None = None,
    world_datetime_from: str | None = None,
    world_datetime_to: str | None = None,
    event_type: str | None = None,
    agent_id: str | None = None,
    limit: int = DEFAULT_TIMELINE_LIMIT,
    offset: int = 0,
    order_desc: bool = False,
    session: AsyncSession = Depends(get_db_session),
) -> TimelineResponse:
    logger.debug(
        f"Getting timeline for run {run_id}, tick_range=[{tick_from}, {tick_to}], limit={limit}"
    )
    run = await get_required_run(session, run_id)

    agent_repo = AgentRepository(session)
    location_repo = LocationRepository(session)
    event_repo = EventRepository(session)

    agents, locations = await asyncio.gather(
        agent_repo.list_names_for_run(str(run_id)),
        location_repo.list_names_for_run(str(run_id)),
    )
    agent_name_map, location_name_map = build_name_maps(agents, locations)
    world_start = resolve_world_start(run)
    tick_minutes = run.tick_minutes or 5
    resolved_tick_from = resolve_tick_bound(
        world_datetime_from, world_start, tick_minutes, tick_from, prefer_min=True
    )
    resolved_tick_to = resolve_tick_bound(
        world_datetime_to, world_start, tick_minutes, tick_to, prefer_min=False
    )

    resolved_agent_id = agent_id
    if agent_id and agent_id not in agent_name_map:
        for agent in agents:
            if agent.name.lower() == agent_id.lower():
                resolved_agent_id = agent.id
                break

    events, total = await event_repo.list_timeline_api_rows(
        run_id=str(run_id),
        tick_from=resolved_tick_from,
        tick_to=resolved_tick_to,
        event_type=event_type,
        actor_agent_id=resolved_agent_id,
        limit=limit,
        offset=offset,
        order_desc=order_desc,
    )

    current_world_time = get_run_world_time(run)

    logger.debug(f"Timeline retrieved for run {run_id}: total={total}, filtered={len(events)}")
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
            build_timeline_event_response(
                event,
                agent_name_map,
                location_name_map,
                world_start,
                tick_minutes,
            )
            for event in events
        ],
    )


@router.get(
    "/{run_id}/events",
    response_model=WorldEventsResponse,
    summary="获取全量事件",
    description="获取 run 的全量历史事件，包含富字段（actor_name, location_name 等），支持按事件类型过滤和增量查询（since_tick）",
    responses={
        **COMMON_RESPONSES,
        200: {"description": "事件列表", "model": WorldEventsResponse},
    },
)
async def get_run_events(
    run_id: UUID,
    event_type: str | None = None,
    limit: int = 500,
    since_tick: int | None = None,
    session: AsyncSession = Depends(get_db_session),
) -> WorldEventsResponse:
    logger.debug(
        f"Getting events for run {run_id}, type={event_type}, limit={limit}, since_tick={since_tick}"
    )
    await get_required_run(session, run_id)

    agent_repo = AgentRepository(session)
    location_repo = LocationRepository(session)
    event_repo = EventRepository(session)
    agents, locations, events = await asyncio.gather(
        agent_repo.list_names_for_run(str(run_id)),
        location_repo.list_names_for_run(str(run_id)),
        event_repo.list_api_rows_for_run(str(run_id), limit=limit, since_tick=since_tick),
    )

    agent_name_map, location_name_map = build_name_maps(agents, locations)

    if event_type:
        if event_type == "social":
            filter_types = {
                "talk",
                "speech",
                "listen",
                "conversation_started",
                "conversation_joined",
            }
        elif event_type == "movement":
            filter_types = {"move"}
        elif event_type == "activity":
            filter_types = {"work", "rest"}
        else:
            filter_types = {event_type}
        events = [event for event in events if event.event_type in filter_types]

    result_events = [
        build_world_event_response(event, agent_name_map, location_name_map) for event in events
    ]
    latest_tick = max((event.tick_no for event in events), default=0)
    logger.debug(
        f"Events retrieved for run {run_id}: total={len(result_events)}, latest_tick={latest_tick}"
    )
    return WorldEventsResponse(
        run_id=str(run_id),
        events=result_events,
        total=len(result_events),
        latest_tick=latest_tick,
    )


@router.get(
    "/{run_id}/world/pulse",
    response_model=WorldPulseResponse,
    summary="获取世界脉冲",
    description="获取世界的高频增量信息，包括运行状态、时钟、最近事件和统计，适合高频轮询。",
    responses={
        **COMMON_RESPONSES,
        200: {"description": "世界脉冲", "model": WorldPulseResponse},
    },
)
async def get_world_pulse(
    run_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> WorldPulseResponse:
    logger.debug(f"Getting world pulse for run {run_id}")
    run = await get_required_run(session, run_id)

    event_repo = EventRepository(session)
    llm_call_repo = LlmCallRepository(session)

    all_time_event_counts, token_totals = await asyncio.gather(
        event_repo.count_events_by_type(
            str(run_id),
            tick_from=None,
            tick_to=None,
            event_types=["speech", "talk", "listen", "move", "move_rejected", "talk_rejected"],
        ),
        llm_call_repo.get_token_totals(str(run_id)),
    )

    world_time = get_run_world_time(run)

    social_speech_count = all_time_event_counts.get("speech", 0) + all_time_event_counts.get(
        "talk", 0
    )

    return WorldPulseResponse(
        run=build_run_snapshot(run),
        world_clock=build_world_clock(world_time),
        daily_stats=WorldDailyStatsResponse(
            talk_count=social_speech_count,
            move_count=all_time_event_counts.get("move", 0),
            rejection_count=all_time_event_counts.get("move_rejected", 0)
            + all_time_event_counts.get("talk_rejected", 0),
            total_input_tokens=token_totals.get("input_tokens", 0),
            total_output_tokens=token_totals.get("output_tokens", 0),
            total_cache_read_tokens=token_totals.get("cache_read_tokens", 0),
            total_cache_creation_tokens=token_totals.get("cache_creation_tokens", 0),
        ),
    )


@router.get(
    "/{run_id}/world",
    response_model=WorldSnapshotResponse,
    summary="获取世界快照",
    description="获取模拟世界的实时快照，包括地点、agent 分布和最近事件",
    responses={
        **COMMON_RESPONSES,
        200: {"description": "世界快照", "model": WorldSnapshotResponse},
    },
)
async def get_world_snapshot(
    run_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> WorldSnapshotResponse:
    logger.debug(f"Getting world snapshot for run {run_id}")
    run = await get_required_run(session, run_id)

    agent_repo = AgentRepository(session)
    location_repo = LocationRepository(session)
    event_repo = EventRepository(session)
    director_memory_repo = DirectorMemoryRepository(session)
    llm_call_repo = LlmCallRepository(session)

    (
        agents,
        locations,
        events,
        director_total,
        director_executed,
        all_time_event_counts,
        token_totals,
    ) = await asyncio.gather(
        agent_repo.list_world_rows_for_run(str(run_id)),
        location_repo.list_world_rows_for_run(str(run_id)),
        event_repo.list_api_rows_for_run(str(run_id), limit=WORLD_RECENT_EVENT_LIMIT),
        director_memory_repo.count_for_run(str(run_id)),
        director_memory_repo.count_executed_for_run(str(run_id)),
        event_repo.count_events_by_type(
            str(run_id),
            tick_from=None,
            tick_to=None,
            event_types=["speech", "talk", "listen", "move", "move_rejected", "talk_rejected"],
        ),
        llm_call_repo.get_token_totals(str(run_id)),
    )

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
    occupants_by_location = build_occupants_by_location(agents)
    locations_payload = [
        WorldLocationResponse(
            id=location.id,
            name=location.name,
            location_type=location.location_type,
            x=location.x,
            y=location.y,
            capacity=location.capacity,
            occupants=[
                agent_summaries[agent.id] for agent in occupants_by_location.get(location.id, [])
            ],
        )
        for location in locations
    ]

    world_time = get_run_world_time(run)
    agent_name_map, location_name_map = build_name_maps(agents, locations)

    social_speech_count = all_time_event_counts.get("speech", 0) + all_time_event_counts.get(
        "talk", 0
    )

    logger.debug(
        f"World snapshot retrieved for run {run_id}: "
        f"agents={len(agents)}, locations={len(locations)}, events={len(events)}, "
        f"director_stats={director_executed}/{director_total}"
    )
    return WorldSnapshotResponse(
        run=build_run_snapshot(run),
        world_clock=build_world_clock(world_time),
        locations=locations_payload,
        recent_events=[
            build_world_event_response(event, agent_name_map, location_name_map)
            for event in events
            if event.visibility == "public"
        ],
        director_stats=WorldDirectorStatsResponse(
            total=director_total,
            executed=director_executed,
            execution_rate=round((director_executed / director_total) * 100)
            if director_total > 0
            else 0,
        ),
        daily_stats=WorldDailyStatsResponse(
            talk_count=social_speech_count,
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
