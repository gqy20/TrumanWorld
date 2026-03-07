from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db import get_db_session
from app.sim.service import SimulationService
from app.store.models import SimulationRun
from app.store.repositories import EventRepository, RunRepository

router = APIRouter()


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
    repo = RunRepository(session)
    run = SimulationRun(id=str(uuid4()), name=payload.name, status="draft")
    created = await repo.create(run)
    if payload.seed_demo:
        service = SimulationService(session)
        await service.seed_demo_run(created.id)
    return RunResponse(id=UUID(created.id), name=created.name, status=created.status)


@router.get("", response_model=list[RunResponse])
async def list_runs(
    session: AsyncSession = Depends(get_db_session),
) -> list[RunResponse]:
    repo = RunRepository(session)
    runs = await repo.list()
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
    repo = RunRepository(session)
    run = await repo.get(str(run_id))
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    service = SimulationService(session)
    result = await service.run_tick(str(run_id))
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
