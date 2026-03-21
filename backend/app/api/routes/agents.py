from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import api_error
from app.api.schemas.simulation import (
    COMMON_RESPONSES,
    AgentDetailResponse,
    AgentEventResponse,
    AgentGovernanceRecordsResponse,
    AgentMemoryResponse,
    AgentRelationshipResponse,
    AgentsListResponse,
    AgentSummaryResponse,
    GovernanceRecordResponse,
    WorldRulesSummaryResponse,
)
from app.infra.db import get_db_session
from app.infra.logging import get_logger
from app.scenario.types import get_agent_config_id
from app.sim.context import ContextBuilder as SimulationContextBuilder
from app.store.repositories import (
    AgentRepository,
    GovernanceRecordRepository,
    LocationRepository,
    RunRepository,
)

router = APIRouter()
logger = get_logger(__name__)


@router.get(
    "",
    response_model=AgentsListResponse,
    summary="列出所有 Agent",
    description="获取指定运行中所有 agent 的基本信息列表",
    responses=COMMON_RESPONSES,
)
async def list_agents(
    run_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> AgentsListResponse:
    logger.debug(f"Listing agents for run {run_id}")
    run_repo = RunRepository(session)
    run = await run_repo.get(str(run_id))
    if run is None:
        raise api_error(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found",
            code="RUN_NOT_FOUND",
            context={"run_id": str(run_id)},
        )

    repo = AgentRepository(session)
    agents = await repo.list_world_rows_for_run(str(run_id))
    logger.debug(f"Retrieved {len(agents)} agents for run {run_id}")

    return AgentsListResponse(
        run_id=str(run_id),
        agents=[
            AgentSummaryResponse(
                id=agent.id,
                name=agent.name,
                occupation=agent.occupation,
                current_goal=agent.current_goal,
                current_location_id=agent.current_location_id,
                config_id=get_agent_config_id(agent.profile),
            )
            for agent in agents
        ],
    )


@router.get(
    "/{agent_id}",
    response_model=AgentDetailResponse,
    summary="获取 Agent 详情",
    description="""
**获取 Agent 完整信息**

返回指定 agent 的详细信息，包括：
- 基本状态（名称、职业、状态、当前目标）
- 最近事件（带 agent 和地点名称）
- 记忆列表（短期、情景、反思）
- 关系网络（熟悉度、信任度、亲和力）
    """,
    responses={
        **COMMON_RESPONSES,
        200: {
            "description": "Agent 详情",
            "model": AgentDetailResponse,
        },
    },
)
async def get_agent(
    run_id: UUID,
    agent_id: str,
    event_type: str | None = Query(None, description="按事件类型过滤"),
    event_query: str | None = Query(None, description="按事件类型或负载文本模糊匹配"),
    include_routine_events: bool = Query(True, description="是否包含 work/rest 等例行事件"),
    event_limit: int = Query(10, ge=1, le=100, description="返回事件条数上限"),
    memory_type: str | None = Query(None, description="按记忆类型过滤"),
    memory_category: str | None = Query(None, description="按记忆层级过滤"),
    memory_query: str | None = Query(None, description="按记忆内容或摘要模糊匹配"),
    min_memory_importance: float | None = Query(None, ge=0.0, le=1.0, description="最低记忆重要性"),
    related_agent_id: str | None = Query(None, description="按关联 agent 过滤记忆"),
    memory_limit: int = Query(10, ge=1, le=100, description="返回记忆条数上限"),
    session: AsyncSession = Depends(get_db_session),
) -> AgentDetailResponse:
    logger.debug(f"Getting agent details: run_id={run_id}, agent_id={agent_id}")
    run_repo = RunRepository(session)
    run = await run_repo.get(str(run_id))
    if run is None:
        raise api_error(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found",
            code="RUN_NOT_FOUND",
            context={"run_id": str(run_id)},
        )

    repo = AgentRepository(session)
    agent = await repo.get(agent_id)
    if agent is None or agent.run_id != str(run_id):
        logger.warning(f"Agent not found: run_id={run_id}, agent_id={agent_id}")
        raise api_error(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
            code="AGENT_NOT_FOUND",
            context={"run_id": str(run_id), "agent_id": agent_id},
        )

    # Build name maps for friendly display
    all_agents = await repo.list_names_for_run(str(run_id))
    agent_name_map = {a.id: a.name for a in all_agents}

    location_repo = LocationRepository(session)
    all_locations = await location_repo.list_names_for_run(str(run_id))
    location_name_map = {loc.id: loc.name for loc in all_locations}

    memories = await repo.list_recent_memories(
        agent_id,
        limit=memory_limit,
        memory_type=memory_type,
        memory_category=memory_category,
        min_importance=min_memory_importance,
        query=memory_query,
        related_agent_id=related_agent_id,
    )
    recent_events = await repo.list_recent_events(
        str(run_id),
        agent_id,
        limit=event_limit,
        event_type=event_type,
        query=event_query,
        include_routine_events=include_routine_events,
    )
    relationships = await repo.list_relationships(str(run_id), agent_id)
    world_rules_summary = await _build_world_rules_summary(
        session=session,
        run=run,
        agent=agent,
        recent_events=recent_events,
    )

    return AgentDetailResponse(
        run_id=str(run_id),
        agent_id=agent_id,
        name=agent.name,
        occupation=agent.occupation,
        status=agent.status or {},
        current_goal=agent.current_goal,
        config_id=get_agent_config_id(agent.profile),
        personality=agent.personality or {},
        profile=agent.profile or {},
        recent_events=[
            AgentEventResponse(
                id=event.id,
                tick_no=event.tick_no,
                event_type=event.event_type,
                actor_agent_id=event.actor_agent_id,
                actor_name=agent_name_map.get(event.actor_agent_id, event.actor_agent_id),
                target_agent_id=event.target_agent_id,
                target_name=(
                    agent_name_map.get(event.target_agent_id, event.target_agent_id)
                    if event.target_agent_id
                    else None
                ),
                location_id=event.location_id,
                location_name=(
                    location_name_map.get(event.location_id, event.location_id)
                    if event.location_id
                    else None
                ),
                payload=event.payload or {},
            )
            for event in recent_events
        ],
        memories=[
            AgentMemoryResponse(
                id=memory.id,
                memory_type=memory.memory_type,
                memory_category=memory.memory_category,
                summary=memory.summary,
                content=memory.content,
                importance=memory.importance,
                event_importance=memory.event_importance,
                self_relevance=memory.self_relevance,
                streak_count=memory.streak_count or 1,
                related_agent_id=memory.related_agent_id,
                related_agent_name=(
                    agent_name_map.get(memory.related_agent_id, memory.related_agent_id)
                    if memory.related_agent_id
                    else None
                ),
            )
            for memory in memories
        ],
        relationships=[
            AgentRelationshipResponse(
                other_agent_id=relation.other_agent_id,
                other_agent_name=agent_name_map.get(
                    relation.other_agent_id, relation.other_agent_id
                ),
                familiarity=relation.familiarity,
                trust=relation.trust,
                affinity=relation.affinity,
                relation_type=relation.relation_type,
            )
            for relation in relationships
        ],
        world_rules_summary=WorldRulesSummaryResponse.model_validate(world_rules_summary),
    )
    logger.debug(
        f"Agent details retrieved: run_id={run_id}, agent_id={agent_id}, "
        f"memories={len(memories)}, events={len(recent_events)}, relationships={len(relationships)}"
    )


@router.get(
    "/{agent_id}/governance-records",
    response_model=AgentGovernanceRecordsResponse,
    summary="获取 Agent 治理记录",
    description="查询指定 agent 最近收到的治理/执法 ledger 记录。",
    responses={
        **COMMON_RESPONSES,
        200: {
            "description": "Agent 治理记录",
            "model": AgentGovernanceRecordsResponse,
        },
    },
)
async def get_agent_governance_records(
    run_id: UUID,
    agent_id: str,
    limit: int = Query(20, ge=1, le=100, description="返回记录条数上限"),
    session: AsyncSession = Depends(get_db_session),
) -> AgentGovernanceRecordsResponse:
    logger.debug(f"Getting agent governance records: run_id={run_id}, agent_id={agent_id}")
    run_repo = RunRepository(session)
    run = await run_repo.get(str(run_id))
    if run is None:
        raise api_error(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found",
            code="RUN_NOT_FOUND",
            context={"run_id": str(run_id)},
        )

    agent_repo = AgentRepository(session)
    agent = await agent_repo.get(agent_id)
    if agent is None or agent.run_id != str(run_id):
        raise api_error(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
            code="AGENT_NOT_FOUND",
            context={"run_id": str(run_id), "agent_id": agent_id},
        )

    location_repo = LocationRepository(session)
    all_locations = await location_repo.list_names_for_run(str(run_id))
    location_name_map = {loc.id: loc.name for loc in all_locations}

    governance_repo = GovernanceRecordRepository(session)
    records = await governance_repo.list_for_agent(str(run_id), agent_id, limit=limit)

    return AgentGovernanceRecordsResponse(
        run_id=str(run_id),
        agent_id=agent_id,
        records=[
            GovernanceRecordResponse(
                id=record.id,
                tick_no=record.tick_no,
                source_event_id=record.source_event_id,
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


async def _build_world_rules_summary(
    *,
    session: AsyncSession,
    run,
    agent,
    recent_events: list,
) -> dict:
    context_builder = SimulationContextBuilder(session)
    world = await context_builder.load_world(str(run.id), run, run.tick_minutes)
    current_location_id = agent.current_location_id or agent.home_location_id
    nearby_agent_id = (
        context_builder.find_nearby_agent(world, agent.id, current_location_id)
        if current_location_id
        else None
    )
    context = context_builder.build_agent_world_context(
        world=world,
        current_goal=agent.current_goal,
        current_location_id=current_location_id,
        home_location_id=agent.home_location_id,
        nearby_agent_id=nearby_agent_id,
        current_status=agent.status or {},
        subject_alert_score=None,
        world_role=(agent.profile or {}).get("world_role"),
        workplace_location_id=(agent.profile or {}).get("workplace_location_id"),
        relationship_context=world.relationship_contexts.get(agent.id),
        recent_events=[
            {
                "event_type": event.event_type,
                "tick_no": event.tick_no,
                "actor_agent_id": event.actor_agent_id,
                "target_agent_id": event.target_agent_id,
                "payload": event.payload or {},
            }
            for event in recent_events
        ],
    )
    return context.get("world_rules_summary") or {}
