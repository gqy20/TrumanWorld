import asyncio
import json
from time import monotonic
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.presenters.world import (
    build_timeline_event_response,
    build_world_clock,
    build_world_event_response,
)
from app.api.routes.runs import build_run_payload, get_required_run
from app.api.schemas.simulation import (
    COMMON_RESPONSES,
    AgentSummaryResponse,
    TimelineResponse,
    TimelineRunInfo,
    WorldDailyStatsResponse,
    WorldDirectorStatsResponse,
    WorldEventsResponse,
    WorldHealthMetricsConfig,
    WorldLocationResponse,
    WorldMapTopologyResponse,
    WorldPulseResponse,
    WorldStageAgentStatusVisualResponse,
    WorldStageAgentUiResponse,
    WorldStagePaletteResponse,
    WorldSnapshotResponse,
    WorldSnapshotRunResponse,
    WorldStageLocationVisualResponse,
    WorldStageUiResponse,
    WorldUiConfigResponse,
)
from app.infra.db import get_db_session
from app.infra.logging import get_logger
from app.scenario.bundle_registry import load_ui_config_for_scenario, load_world_config_for_scenario
from app.scenario.runtime_config import build_scenario_runtime_config
from app.scenario.types import get_agent_config_id
from app.sim.context import get_run_world_time
from app.sim.movement import AgentMovementState
from app.sim.world_map import build_world_map
from app.sim.world_time import resolve_tick_bound, resolve_world_start
from app.store.repositories import (
    AgentRepository,
    EventRepository,
    LocationRepository,
    WorldStatsRepository,
)

router = APIRouter()
logger = get_logger(__name__)

DEFAULT_TIMELINE_LIMIT = 500
WORLD_RECENT_EVENT_LIMIT = 60
EVENT_STREAM_BATCH_LIMIT = 100
EVENT_STREAM_POLL_SECONDS = 1.0
EVENT_STREAM_HEARTBEAT_SECONDS = 15.0
EVENT_STREAM_MAX_TRACKED_IDS = 2048


def build_name_maps(agents, locations) -> tuple[dict[str, str], dict[str, str]]:
    return (
        {agent.id: agent.name for agent in agents},
        {location.id: location.name for location in locations},
    )


def build_occupants_by_location(agents) -> dict[str, list]:
    occupants_by_location: dict[str, list] = {}
    for agent in agents:
        if not agent.current_location_id or AgentMovementState.from_dict(agent.movement):
            continue
        occupants_by_location.setdefault(agent.current_location_id, []).append(agent)
    return occupants_by_location


def resolve_subject_agent_id(agents, scenario_type: str | None) -> str | None:
    runtime_config = build_scenario_runtime_config(scenario_type)
    subject_role = runtime_config.subject_role
    for agent in agents:
        if (agent.profile or {}).get("world_role") == subject_role:
            return agent.id
    return None


def build_run_snapshot(run) -> WorldSnapshotRunResponse:
    return WorldSnapshotRunResponse(**build_run_payload(run))


def _build_health_metrics_config(scenario_type: str | None) -> WorldHealthMetricsConfig:
    try:
        world_cfg = load_world_config_for_scenario(scenario_type)
        ui_cfg = load_ui_config_for_scenario(scenario_type)
        cfg = world_cfg.get("health_metrics", {})
        cont = cfg.get("continuity", {})
        soc = cfg.get("social", {})
        heat = world_cfg.get("location_heat", {})
        thresholds = heat.get("thresholds", {})
        ui = ui_cfg or world_cfg.get("ui_config", {})
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


def _build_world_ui_config(scenario_type: str | None) -> WorldUiConfigResponse:
    try:
        ui_cfg = load_ui_config_for_scenario(scenario_type) or {}
        stage_cfg = ui_cfg.get("stage", {})
        location_type_cfg = stage_cfg.get("location_types", {})
        agent_status_cfg = (stage_cfg.get("agents") or {}).get("statuses", {})
        palette_cfg = stage_cfg.get("palette", {})
        return WorldUiConfigResponse(
            stage=WorldStageUiResponse(
                renderer=stage_cfg.get("renderer"),
                theme=stage_cfg.get("theme"),
                ground_preset=stage_cfg.get("ground_preset"),
                palette=WorldStagePaletteResponse(
                    background_color=palette_cfg.get("background_color"),
                    header_color=palette_cfg.get("header_color"),
                    header_alpha=palette_cfg.get("header_alpha"),
                    vignette_color=palette_cfg.get("vignette_color"),
                    vignette_alpha=palette_cfg.get("vignette_alpha"),
                    label_color=palette_cfg.get("label_color"),
                ),
                agents=WorldStageAgentUiResponse(
                    statuses={
                        status: WorldStageAgentStatusVisualResponse(
                            visual_preset=(config or {}).get("visual_preset"),
                            marker=(config or {}).get("marker"),
                        )
                        for status, config in agent_status_cfg.items()
                        if isinstance(config, dict)
                    }
                ),
                location_types={
                    location_type: WorldStageLocationVisualResponse(
                        visual_preset=(config or {}).get("visual_preset"),
                        glyph=(config or {}).get("glyph"),
                    )
                    for location_type, config in location_type_cfg.items()
                    if isinstance(config, dict)
                },
            )
        )
    except Exception:
        return WorldUiConfigResponse()


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

    agents = await agent_repo.list_names_for_run(str(run_id))
    locations = await location_repo.list_names_for_run(str(run_id))
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

    events, filtered_total = await event_repo.list_timeline_api_rows(
        run_id=str(run_id),
        tick_from=resolved_tick_from,
        tick_to=resolved_tick_to,
        event_type=event_type,
        actor_agent_id=resolved_agent_id,
        limit=limit,
        offset=offset,
        order_desc=order_desc,
    )
    total = await event_repo.count_for_run(str(run_id))

    current_world_time = get_run_world_time(run)

    logger.debug(
        f"Timeline retrieved for run {run_id}: total={total}, "
        f"filtered={filtered_total}, page_size={len(events)}"
    )
    return TimelineResponse(
        run_id=str(run_id),
        total=total,
        filtered=filtered_total,
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
    agents = await agent_repo.list_names_for_run(str(run_id))
    locations = await location_repo.list_names_for_run(str(run_id))
    events = await event_repo.list_api_rows_for_run(str(run_id), limit=limit, since_tick=since_tick)

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
            filter_types = {"move", "move_arrived"}
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
    "/{run_id}/events/stream",
    summary="订阅实时世界事件",
    description="使用 Server-Sent Events 推送公开世界事件；世界快照仍是位置状态的最终依据。",
    responses={
        **COMMON_RESPONSES,
        200: {"description": "text/event-stream 世界事件流"},
    },
)
async def stream_run_events(
    run_id: UUID,
    request: Request,
    since_tick: int = 0,
    session: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    await get_required_run(session, run_id)
    agents = await AgentRepository(session).list_names_for_run(str(run_id))
    locations = await LocationRepository(session).list_names_for_run(str(run_id))
    agent_name_map, location_name_map = build_name_maps(agents, locations)
    await session.rollback()

    async def generate_event_stream():
        cursor_tick = max(0, since_tick)
        known_event_ids: set[str] = set()
        last_heartbeat_at = monotonic()
        event_repo = EventRepository(session)

        yield "retry: 3000\n\n"
        try:
            while not await request.is_disconnected():
                events = list(
                    await event_repo.list_api_rows_for_run(
                        str(run_id),
                        limit=EVENT_STREAM_BATCH_LIMIT,
                        since_tick=max(-1, cursor_tick - 1),
                    )
                )
                await session.rollback()
                if events:
                    cursor_tick = max(cursor_tick, max(event.tick_no for event in events))

                pending_events = sorted(
                    (
                        event
                        for event in events
                        if event.visibility == "public"
                        and event.tick_no >= max(0, since_tick)
                        and event.id not in known_event_ids
                    ),
                    key=lambda event: (event.tick_no, event.id),
                )
                for event in pending_events:
                    known_event_ids.add(event.id)
                    payload = build_world_event_response(
                        event,
                        agent_name_map,
                        location_name_map,
                    ).model_dump(mode="json")
                    yield _encode_sse_world_event(event.id, payload)

                if len(known_event_ids) > EVENT_STREAM_MAX_TRACKED_IDS:
                    known_event_ids.intersection_update(event.id for event in events)

                now = monotonic()
                if not pending_events and now - last_heartbeat_at >= EVENT_STREAM_HEARTBEAT_SECONDS:
                    yield ": keep-alive\n\n"
                    last_heartbeat_at = now
                elif pending_events:
                    last_heartbeat_at = now

                await asyncio.sleep(EVENT_STREAM_POLL_SECONDS)
        finally:
            if session.in_transaction():
                await session.rollback()

    return StreamingResponse(
        generate_event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _encode_sse_world_event(event_id: str, payload: dict) -> str:
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"id: {event_id}\nevent: world_event\ndata: {data}\n\n"


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

    stats = await WorldStatsRepository(session).get_for_run(str(run_id))
    all_time_event_counts = stats.event_counts
    token_totals = stats.token_totals

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
            total_reasoning_tokens=token_totals.get("reasoning_tokens", 0),
            total_cache_read_tokens=token_totals.get("cache_read_tokens", 0),
            total_cache_creation_tokens=token_totals.get("cache_creation_tokens", 0),
            llm_provider=token_totals.get("provider"),
            llm_model=token_totals.get("model"),
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

    agents = await agent_repo.list_world_rows_for_run(str(run_id))
    locations = await location_repo.list_world_rows_for_run(str(run_id))
    events = await event_repo.list_api_rows_for_run(str(run_id), limit=WORLD_RECENT_EVENT_LIMIT)
    stats = await WorldStatsRepository(session).get_for_run(str(run_id))
    director_total = stats.director_total
    director_executed = stats.director_executed
    all_time_event_counts = stats.event_counts
    token_totals = stats.token_totals

    agent_summaries = {}
    for agent in agents:
        movement = AgentMovementState.from_dict(agent.movement)
        agent_summaries[agent.id] = AgentSummaryResponse(
            id=agent.id,
            name=agent.name,
            occupation=agent.occupation,
            current_goal=agent.current_goal,
            current_location_id=None if movement else agent.current_location_id,
            movement=movement.to_dict() if movement else None,
            status=agent.status or {},
            profile=agent.profile or {},
            config_id=get_agent_config_id(agent.profile),
        )
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
        subject_agent_id=resolve_subject_agent_id(agents, run.scenario_type),
        agents=list(agent_summaries.values()),
        locations=locations_payload,
        navigation=WorldMapTopologyResponse(**build_world_map(locations).to_dict()),
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
            total_reasoning_tokens=token_totals.get("reasoning_tokens", 0),
            total_cache_read_tokens=token_totals.get("cache_read_tokens", 0),
            total_cache_creation_tokens=token_totals.get("cache_creation_tokens", 0),
            llm_provider=token_totals.get("provider"),
            llm_model=token_totals.get("model"),
        ),
        health_metrics_config=_build_health_metrics_config(run.scenario_type),
        ui_config=_build_world_ui_config(run.scenario_type),
    )
