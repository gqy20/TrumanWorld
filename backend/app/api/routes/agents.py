from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.simulation import (
    COMMON_RESPONSES,
    AgentDetailResponse,
    AgentEventResponse,
    AgentMemoryResponse,
    AgentRelationshipResponse,
    AgentsListResponse,
    AgentSummaryResponse,
)
from app.infra.db import get_db_session
from app.infra.logging import get_logger
from app.scenario.truman_world.types import get_agent_config_id
from app.store.repositories import (
    AgentRepository,
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

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
    session: AsyncSession = Depends(get_db_session),
) -> AgentDetailResponse:
    logger.debug(f"Getting agent details: run_id={run_id}, agent_id={agent_id}")
    run_repo = RunRepository(session)
    run = await run_repo.get(str(run_id))
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    repo = AgentRepository(session)
    agent = await repo.get(agent_id)
    if agent is None or agent.run_id != str(run_id):
        logger.warning(f"Agent not found: run_id={run_id}, agent_id={agent_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    # Build name maps for friendly display
    all_agents = await repo.list_names_for_run(str(run_id))
    agent_name_map = {a.id: a.name for a in all_agents}

    location_repo = LocationRepository(session)
    all_locations = await location_repo.list_names_for_run(str(run_id))
    location_name_map = {loc.id: loc.name for loc in all_locations}

    memories = await repo.list_recent_memories(agent_id)
    recent_events = await repo.list_recent_events(str(run_id), agent_id)
    relationships = await repo.list_relationships(str(run_id), agent_id)

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
    )
    logger.debug(
        f"Agent details retrieved: run_id={run_id}, agent_id={agent_id}, "
        f"memories={len(memories)}, events={len(recent_events)}, relationships={len(relationships)}"
    )
