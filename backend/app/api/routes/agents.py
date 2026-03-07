from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db import get_db_session
from app.store.repositories import AgentRepository, RunRepository

router = APIRouter()


@router.get("/{agent_id}")
async def get_agent(
    run_id: UUID,
    agent_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, object]:
    run_repo = RunRepository(session)
    run = await run_repo.get(str(run_id))
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    repo = AgentRepository(session)
    agent = await repo.get(agent_id)
    if agent is None or agent.run_id != str(run_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    memories = await repo.list_recent_memories(agent_id)
    recent_events = await repo.list_recent_events(str(run_id), agent_id)
    relationships = await repo.list_relationships(str(run_id), agent_id)

    return {
        "run_id": str(run_id),
        "agent_id": agent_id,
        "name": agent.name,
        "occupation": agent.occupation,
        "status": agent.status,
        "current_goal": agent.current_goal,
        "recent_events": [
            {
                "id": event.id,
                "tick_no": event.tick_no,
                "event_type": event.event_type,
                "payload": event.payload,
            }
            for event in recent_events
        ],
        "memories": [
            {
                "id": memory.id,
                "memory_type": memory.memory_type,
                "summary": memory.summary,
                "content": memory.content,
                "importance": memory.importance,
            }
            for memory in memories
        ],
        "relationships": [
            {
                "other_agent_id": relation.other_agent_id,
                "familiarity": relation.familiarity,
                "trust": relation.trust,
                "affinity": relation.affinity,
                "relation_type": relation.relation_type,
            }
            for relation in relationships
        ],
    }
