import asyncio
import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.runs import get_required_run
from app.api.schemas.simulation import (
    COMMON_RESPONSES,
    DirectorEventRequest,
    DirectorMemoriesResponse,
    DirectorMemoryResponse,
    DirectorObservationResponse,
    StatusResponse,
)
from app.director.service import DirectorEventService
from app.infra.db import get_db_session
from app.sim.service import SimulationService
from app.store.repositories import (
    AgentRepository,
    DirectorMemoryRepository,
    LocationRepository,
)

router = APIRouter()


def serialize_director_memory(
    memory,
    *,
    current_tick: int,
    agent_name_map: dict[str, str],
    location_name_map: dict[str, str],
    manual_goals: set[str],
) -> DirectorMemoryResponse:
    target_cast_ids = json.loads(memory.target_cast_ids) if memory.target_cast_ids else []
    location_hint = memory.metadata_json.get("location_hint") if memory.metadata_json else None
    if memory.was_executed:
        delivery_status = "consumed"
    elif memory.scene_goal in manual_goals and current_tick > memory.tick_no + 5:
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
        target_agent_name=agent_name_map.get(memory.target_agent_id)
        if memory.target_agent_id
        else None,
        target_cast_ids=target_cast_ids,
        target_cast_names=[agent_name_map.get(agent_id, agent_id) for agent_id in target_cast_ids],
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


@router.get(
    "/{run_id}/director/observation",
    response_model=DirectorObservationResponse,
    summary="获取导演观察",
    description="获取只读导演观察结果，包括 Truman 怀疑度和世界连续性风险",
    responses={
        **COMMON_RESPONSES,
        200: {"description": "导演观察结果", "model": DirectorObservationResponse},
    },
)
async def get_director_observation(
    run_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> DirectorObservationResponse:
    await get_required_run(session, run_id)
    assessment = await SimulationService(session).observe_run(str(run_id))
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
    description="获取导演干预计划明细，支持前端查看全部、排队中、已消费和已过期记录。",
    responses={
        **COMMON_RESPONSES,
        200: {"description": "导演干预明细", "model": DirectorMemoriesResponse},
    },
)
async def get_director_memories(
    run_id: UUID,
    limit: int = 50,
    session: AsyncSession = Depends(get_db_session),
) -> DirectorMemoriesResponse:
    run = await get_required_run(session, run_id)

    agent_repo = AgentRepository(session)
    location_repo = LocationRepository(session)
    director_memory_repo = DirectorMemoryRepository(session)

    agents, locations, memories = await asyncio.gather(
        agent_repo.list_names_for_run(str(run_id)),
        location_repo.list_names_for_run(str(run_id)),
        director_memory_repo.list_for_run(str(run_id), limit=limit),
    )

    agent_name_map = {agent.id: agent.name for agent in agents}
    location_name_map = {location.id: location.name for location in locations}
    manual_goals = {"gather", "activity", "shutdown", "weather_change", "power_outage"}

    return DirectorMemoriesResponse(
        run_id=str(run_id),
        memories=[
            serialize_director_memory(
                memory,
                current_tick=run.current_tick,
                agent_name_map=agent_name_map,
                location_name_map=location_name_map,
                manual_goals=manual_goals,
            )
            for memory in memories
        ],
        total=len(memories),
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
- `power_outage`: 指定地点停电

注意：导演系统仅限于简单世界事件，不允许直接修改 agent 属性或关系。
    """,
    responses={
        **COMMON_RESPONSES,
        200: {"description": "事件注入成功", "model": StatusResponse},
    },
)
async def inject_director_event(
    run_id: UUID,
    payload: DirectorEventRequest,
    session: AsyncSession = Depends(get_db_session),
) -> StatusResponse:
    await get_required_run(session, run_id)
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
