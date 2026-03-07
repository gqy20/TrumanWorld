from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db import get_db_session
from app.infra.logging import debug, error, get_logger, info, warning
from app.sim.scheduler import get_scheduler
from app.sim.service import SimulationService
from app.store.models import SimulationRun
from app.store.repositories import AgentRepository, EventRepository, LocationRepository, RunRepository

router = APIRouter()
logger = get_logger(__name__)


class RunCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    seed_demo: bool = True


class RunResponse(BaseModel):
    id: UUID
    name: str
    status: str


class DirectorEventRequest(BaseModel):
    event_type: str = Field(min_length=1, max_length=50)
    payload: dict = Field(default_factory=dict)
    location_id: str | None = None
    importance: float = Field(default=0.5, ge=0.0, le=1.0)


class TickResponse(BaseModel):
    run_id: UUID
    tick_no: int
    accepted_count: int
    rejected_count: int


@router.post("", response_model=RunResponse)
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
    if not scheduler.is_running(created.id):
        from app.infra.db import async_engine
        
        async def tick_callback(rid: str) -> None:
            from sqlalchemy.ext.asyncio import AsyncSession
            from app.sim.service import SimulationService
            
            async with AsyncSession(async_engine) as new_session:
                service = SimulationService(new_session)
                try:
                    await service.run_tick(rid)
                except RuntimeError as e:
                    # 忽略 claude_agent_sdk 的 cancel scope 错误（任务取消时的正常现象）
                    if "cancel scope" in str(e).lower() or "cancelled" in str(e).lower():
                        logger.debug(f"Tick callback cancelled for run {rid}")
                    else:
                        logger.warning(f"Auto-tick failed for run {rid}: {e}")
                except Exception as e:
                    logger.warning(f"Auto-tick failed for run {rid}: {e}")
        
        await scheduler.start_run(created.id, interval_seconds=5.0, callback=tick_callback)
        logger.info(f"Auto-scheduler started for run {created.id}")
    
    return RunResponse(id=UUID(created.id), name=created.name, status=created.status)


@router.get("", response_model=list[RunResponse])
async def list_runs(
    session: AsyncSession = Depends(get_db_session),
) -> list[RunResponse]:
    logger.debug("Listing all runs")
    repo = RunRepository(session)
    runs = await repo.list()
    logger.debug(f"Found {len(runs)} runs")
    return [RunResponse(id=UUID(run.id), name=run.name, status=run.status) for run in runs]


@router.post("/{run_id}/start", response_model=RunResponse)
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
    if not scheduler.is_running(str(run_id)):
        from app.infra.db import async_engine
        
        async def tick_callback(rid: str) -> None:
            from sqlalchemy.ext.asyncio import AsyncSession
            from app.sim.service import SimulationService
            
            async with AsyncSession(async_engine) as new_session:
                service = SimulationService(new_session)
                try:
                    await service.run_tick(rid)
                except RuntimeError as e:
                    # 忽略 claude_agent_sdk 的 cancel scope 错误（任务取消时的正常现象）
                    if "cancel scope" in str(e).lower() or "cancelled" in str(e).lower():
                        logger.debug(f"Tick callback cancelled for run {rid}")
                    else:
                        logger.warning(f"Auto-tick failed for run {rid}: {e}")
                except Exception as e:
                    logger.warning(f"Auto-tick failed for run {rid}: {e}")
        
        await scheduler.start_run(str(run_id), interval_seconds=5.0, callback=tick_callback)
    
    return RunResponse(id=run_id, name=updated.name, status=updated.status)


@router.post("/{run_id}/pause", response_model=RunResponse)
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
    await scheduler.stop_run(str(run_id))
    
    updated = await repo.update_status(run, "paused")
    return RunResponse(id=run_id, name=updated.name, status=updated.status)


@router.post("/{run_id}/resume", response_model=RunResponse)
async def resume_run(
    run_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> RunResponse:
    repo = RunRepository(session)
    run = await repo.get(str(run_id))
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    updated = await repo.update_status(run, "running")
    return RunResponse(id=run_id, name=updated.name, status=updated.status)


@router.post("/{run_id}/tick", response_model=TickResponse)
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


@router.get("/{run_id}")
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


@router.get("/{run_id}/timeline")
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


@router.get("/{run_id}/world")
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

    return {
        "run": {
            "id": run.id,
            "name": run.name,
            "status": run.status,
            "current_tick": run.current_tick,
            "tick_minutes": run.tick_minutes,
        },
        "locations": locations_payload,
        "recent_events": [
            {
                "id": event.id,
                "tick_no": event.tick_no,
                "event_type": event.event_type,
                "location_id": event.location_id,
                "actor_agent_id": event.actor_agent_id,
                "target_agent_id": event.target_agent_id,
                "payload": event.payload,
            }
            for event in events
            if event.visibility == "public"
        ],
    }


@router.post("/{run_id}/director/events")
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


@router.delete("/{run_id}")
async def delete_run(
    run_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """Delete a run and all its associated data."""
    logger.info(f"Deleting run: {run_id}")
    
    # Stop scheduler if running
    scheduler = get_scheduler()
    await scheduler.stop_run(str(run_id))
    
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
