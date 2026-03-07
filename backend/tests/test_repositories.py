import pytest

from app.store.models import Event, SimulationRun
from app.store.repositories import EventRepository, RunRepository


@pytest.mark.asyncio
async def test_run_repository_create_and_get(db_session):
    repo = RunRepository(db_session)
    run = SimulationRun(id="run-repo-1", name="repo-run", status="draft")

    await repo.create(run)
    fetched = await repo.get("run-repo-1")

    assert fetched is not None
    assert fetched.name == "repo-run"
    assert fetched.status == "draft"


@pytest.mark.asyncio
async def test_event_repository_orders_events_by_tick_desc(db_session):
    run = SimulationRun(id="run-repo-2", name="timeline", status="running")
    db_session.add(run)
    db_session.add_all(
        [
            Event(id="event-a", run_id="run-repo-2", tick_no=1, event_type="move", payload={}),
            Event(id="event-b", run_id="run-repo-2", tick_no=3, event_type="talk", payload={}),
            Event(id="event-c", run_id="run-repo-2", tick_no=2, event_type="rest", payload={}),
        ]
    )
    await db_session.commit()

    repo = EventRepository(db_session)
    events = await repo.list_for_run("run-repo-2")

    assert [event.id for event in events] == ["event-b", "event-c", "event-a"]
