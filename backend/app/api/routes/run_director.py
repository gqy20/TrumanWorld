import json
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.errors import api_error
from app.api.auth import require_demo_admin_access
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.runs import get_required_run
from app.api.schemas.simulation import (
    COMMON_RESPONSES,
    DirectorGovernanceRecordResponse,
    DirectorGovernanceRecordsResponse,
    DirectorEventRequest,
    DirectorDirectiveResponse,
    DirectorDirectivesResponse,
    DirectorMemoriesResponse,
    DirectorMemoryResponse,
    DirectorObservationResponse,
    GovernanceCaseResponse,
    GovernanceCasesResponse,
    GovernanceRestrictionResponse,
    GovernanceRestrictionsResponse,
    StatusResponse,
)
from app.director.service import DirectorEventService
from app.infra.db import get_db_session
from app.sim.service import SimulationService
from app.store.repositories import (
    AgentRepository,
    DirectorMemoryRepository,
    DirectorDirectiveRepository,
    GovernanceCaseRepository,
    GovernanceRecordRepository,
    GovernanceRestrictionRepository,
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
    target_agent_ids = json.loads(memory.target_agent_ids) if memory.target_agent_ids else []
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
        target_agent_ids=target_agent_ids,
        target_agent_names=[
            agent_name_map.get(agent_id, agent_id) for agent_id in target_agent_ids
        ],
        location_hint=location_hint,
        location_name=location_name_map.get(location_hint) if location_hint else None,
        reason=memory.reason,
        was_executed=memory.was_executed,
        delivery_status=delivery_status,
        effectiveness_score=memory.effectiveness_score,
        trigger_subject_alert_score=memory.trigger_subject_alert_score,
        trigger_continuity_risk=memory.trigger_continuity_risk,
        cooldown_ticks=memory.cooldown_ticks,
        cooldown_until_tick=memory.cooldown_until_tick,
        created_at=memory.created_at,
    )


def serialize_director_directive(
    directive,
    *,
    agent_name_map: dict[str, str],
    location_name_map: dict[str, str],
) -> DirectorDirectiveResponse:
    return DirectorDirectiveResponse(
        id=directive.id,
        target_agent_id=directive.target_agent_id,
        target_agent_name=agent_name_map.get(directive.target_agent_id),
        subject_agent_id=directive.subject_agent_id,
        subject_agent_name=agent_name_map.get(directive.subject_agent_id),
        objective=directive.objective,
        mode=directive.mode,
        priority=directive.priority,
        status=directive.status,
        issued_tick=directive.issued_tick,
        expires_at_tick=directive.expires_at_tick,
        completed_tick=directive.completed_tick,
        location_id=directive.location_id,
        location_name=location_name_map.get(directive.location_id),
        message_hint=directive.message_hint,
        constraints=directive.constraints_json or {},
        completion_criteria=directive.completion_criteria_json or {},
        source=directive.source,
        source_memory_id=directive.source_memory_id,
        disposition=directive.disposition,
        failure_reason=directive.failure_reason,
        attempt_count=directive.attempt_count,
        last_attempt_tick=directive.last_attempt_tick,
        last_progress_tick=directive.last_progress_tick,
        last_result_action_type=directive.last_result_action_type,
        last_result_target_agent_id=directive.last_result_target_agent_id,
        replaced_by_directive_id=directive.replaced_by_directive_id,
        created_at=directive.created_at,
        updated_at=directive.updated_at,
    )


@router.get(
    "/{run_id}/director/governance-records",
    response_model=DirectorGovernanceRecordsResponse,
    summary="获取导演治理记录",
    description="获取 run 级治理 ledger，支持导演按 agent 或 decision 查看制度执行历史。",
    responses={
        **COMMON_RESPONSES,
        200: {"description": "导演治理记录", "model": DirectorGovernanceRecordsResponse},
    },
)
async def get_director_governance_records(
    run_id: UUID,
    limit: int = Query(50, ge=1, le=200),
    decision: str | None = Query(None, description="按治理决策过滤"),
    agent_id: str | None = Query(None, description="按 agent 过滤"),
    session: AsyncSession = Depends(get_db_session),
) -> DirectorGovernanceRecordsResponse:
    await get_required_run(session, run_id)

    agent_repo = AgentRepository(session)
    location_repo = LocationRepository(session)
    governance_repo = GovernanceRecordRepository(session)

    agents = await agent_repo.list_names_for_run(str(run_id))
    locations = await location_repo.list_names_for_run(str(run_id))
    records = await governance_repo.list_for_run(
        str(run_id),
        limit=limit,
        decision=decision,
        agent_id=agent_id,
    )

    agent_name_map = {agent.id: agent.name for agent in agents}
    location_name_map = {location.id: location.name for location in locations}

    return DirectorGovernanceRecordsResponse(
        run_id=str(run_id),
        records=[
            DirectorGovernanceRecordResponse(
                id=record.id,
                tick_no=record.tick_no,
                source_event_id=record.source_event_id,
                agent_id=record.agent_id,
                agent_name=agent_name_map.get(record.agent_id),
                location_id=record.location_id,
                location_name=(
                    location_name_map.get(record.location_id, record.location_id)
                    if record.location_id
                    else None
                ),
                action_type=record.action_type,
                decision=record.decision,
                reason=record.reason,
                observed=record.observed,
                observation_score=record.observation_score,
                intervention_score=record.intervention_score,
                metadata=record.metadata_json or {},
            )
            for record in records
        ],
        total=len(records),
    )


@router.get(
    "/{run_id}/director/observation",
    response_model=DirectorObservationResponse,
    summary="获取导演观察",
    description="获取只读导演观察结果，包括主体告警信号（若启用）和世界连续性风险",
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
        subject_agent_id=assessment.subject_agent_id,
        subject_alert_tracking_enabled=assessment.subject_alert_tracking_enabled,
        subject_alert_score=(
            assessment.subject_alert_score if assessment.subject_alert_tracking_enabled else None
        ),
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

    agents = await agent_repo.list_names_for_run(str(run_id))
    locations = await location_repo.list_names_for_run(str(run_id))
    memories = await director_memory_repo.list_for_run(str(run_id), limit=limit)

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


@router.get(
    "/{run_id}/director/directives",
    response_model=DirectorDirectivesResponse,
    summary="获取导演控制指令",
    description="查看 Director 下发给 Actor 的指令、回执及生命周期状态。",
    responses={
        **COMMON_RESPONSES,
        200: {"description": "导演控制指令", "model": DirectorDirectivesResponse},
    },
)
async def get_director_directives(
    run_id: UUID,
    directive_status: Literal["pending", "active", "succeeded", "failed", "expired", "cancelled"]
    | None = Query(None, alias="status"),
    agent_id: str | None = Query(None, description="按执行角色过滤"),
    limit: int = Query(100, ge=1, le=200),
    session: AsyncSession = Depends(get_db_session),
) -> DirectorDirectivesResponse:
    await get_required_run(session, run_id)
    run_id_text = str(run_id)
    directives = await DirectorDirectiveRepository(session).list_for_run(
        run_id_text,
        status=directive_status,
        agent_id=agent_id,
        limit=limit,
    )
    agents = await AgentRepository(session).list_names_for_run(run_id_text)
    locations = await LocationRepository(session).list_names_for_run(run_id_text)
    agent_name_map = {agent.id: agent.name for agent in agents}
    location_name_map = {location.id: location.name for location in locations}
    return DirectorDirectivesResponse(
        run_id=run_id_text,
        directives=[
            serialize_director_directive(
                directive,
                agent_name_map=agent_name_map,
                location_name_map=location_name_map,
            )
            for directive in directives
        ],
        total=len(directives),
    )


@router.get(
    "/{run_id}/director/directives/{directive_id}",
    response_model=DirectorDirectiveResponse,
    summary="获取导演控制指令详情",
    responses={
        **COMMON_RESPONSES,
        200: {"description": "导演控制指令", "model": DirectorDirectiveResponse},
    },
)
async def get_director_directive(
    run_id: UUID,
    directive_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> DirectorDirectiveResponse:
    await get_required_run(session, run_id)
    run_id_text = str(run_id)
    directive = await DirectorDirectiveRepository(session).get_for_run(run_id_text, directive_id)
    if directive is None:
        raise api_error(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Director directive not found",
            code="DIRECTOR_DIRECTIVE_NOT_FOUND",
            context={"run_id": run_id_text, "directive_id": directive_id},
        )
    agents = await AgentRepository(session).list_names_for_run(run_id_text)
    locations = await LocationRepository(session).list_names_for_run(run_id_text)
    return serialize_director_directive(
        directive,
        agent_name_map={agent.id: agent.name for agent in agents},
        location_name_map={location.id: location.name for location in locations},
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
    _: None = Depends(require_demo_admin_access),
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
        raise api_error(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
            code="DIRECTOR_EVENT_INVALID",
            context={"run_id": str(run_id), "event_type": payload.event_type},
        ) from exc
    return StatusResponse(run_id=str(run_id), status="queued")


@router.get(
    "/{run_id}/director/cases",
    response_model=GovernanceCasesResponse,
    summary="获取导演治理案件",
    description="获取 run 级治理案件列表，支持按 agent 或 status 过滤。",
    responses={
        **COMMON_RESPONSES,
        200: {"description": "导演治理案件", "model": GovernanceCasesResponse},
    },
)
async def get_director_governance_cases(
    run_id: UUID,
    agent_id: str | None = Query(None, description="按 agent 过滤"),
    status: str | None = Query(None, description="按案件状态过滤"),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_db_session),
) -> GovernanceCasesResponse:
    await get_required_run(session, run_id)

    agent_repo = AgentRepository(session)
    case_repo = GovernanceCaseRepository(session)

    agents = await agent_repo.list_names_for_run(str(run_id))
    cases = await case_repo.list_for_run(
        str(run_id),
        agent_id=agent_id,
        status=status,
        limit=limit,
    )

    agent_name_map = {agent.id: agent.name for agent in agents}

    return GovernanceCasesResponse(
        run_id=str(run_id),
        cases=[
            GovernanceCaseResponse(
                id=case.id,
                run_id=case.run_id,
                agent_id=case.agent_id,
                agent_name=agent_name_map.get(case.agent_id),
                status=case.status,
                opened_tick=case.opened_tick,
                last_updated_tick=case.last_updated_tick,
                primary_reason=case.primary_reason,
                severity=case.severity,
                record_count=case.record_count,
                active_restriction_count=case.active_restriction_count,
                metadata=case.metadata_json or {},
                created_at=case.created_at,
            )
            for case in cases
        ],
        total=len(cases),
    )


@router.get(
    "/{run_id}/director/restrictions",
    response_model=GovernanceRestrictionsResponse,
    summary="获取导演治理限制",
    description="获取 run 级活跃治理限制列表，支持按 agent 或 restriction_type 过滤。",
    responses={
        **COMMON_RESPONSES,
        200: {"description": "导演治理限制", "model": GovernanceRestrictionsResponse},
    },
)
async def get_director_governance_restrictions(
    run_id: UUID,
    agent_id: str | None = Query(None, description="按 agent 过滤"),
    restriction_type: str | None = Query(None, description="按限制类型过滤"),
    status: str | None = Query(None, description="按限制状态过滤 (active/expired/lifted)"),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_db_session),
) -> GovernanceRestrictionsResponse:
    await get_required_run(session, run_id)

    agent_repo = AgentRepository(session)
    restriction_repo = GovernanceRestrictionRepository(session)

    agents = await agent_repo.list_names_for_run(str(run_id))
    restrictions = await restriction_repo.list_for_run(
        str(run_id),
        agent_id=agent_id,
        restriction_type=restriction_type,
        status=status,
        limit=limit,
    )

    agent_name_map = {agent.id: agent.name for agent in agents}

    return GovernanceRestrictionsResponse(
        run_id=str(run_id),
        restrictions=[
            GovernanceRestrictionResponse(
                id=restriction.id,
                run_id=restriction.run_id,
                agent_id=restriction.agent_id,
                agent_name=agent_name_map.get(restriction.agent_id),
                case_id=restriction.case_id,
                restriction_type=restriction.restriction_type,
                status=restriction.status,
                scope_type=restriction.scope_type,
                scope_value=restriction.scope_value,
                reason=restriction.reason,
                start_tick=restriction.start_tick,
                end_tick=restriction.end_tick,
                severity=restriction.severity,
                metadata=restriction.metadata_json or {},
                created_at=restriction.created_at,
            )
            for restriction in restrictions
        ],
        total=len(restrictions),
    )
