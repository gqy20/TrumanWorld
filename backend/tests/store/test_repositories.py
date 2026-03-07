import pytest

from app.store.models import Event, SimulationRun
from app.store.repositories import EventRepository, RelationshipRepository, RunRepository


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


@pytest.mark.asyncio
async def test_relationship_repository_upserts_and_clamps_values(db_session):
    run = SimulationRun(id="run-repo-3", name="relations", status="running")
    db_session.add(run)
    await db_session.commit()

    repo = RelationshipRepository(db_session)
    relation = await repo.upsert_interaction(
        run_id="run-repo-3",
        agent_id="alice",
        other_agent_id="bob",
        familiarity_delta=0.7,
        trust_delta=0.6,
        affinity_delta=0.4,
    )
    updated = await repo.upsert_interaction(
        run_id="run-repo-3",
        agent_id="alice",
        other_agent_id="bob",
        familiarity_delta=0.7,
        trust_delta=0.7,
        affinity_delta=0.8,
    )

    assert relation.other_agent_id == "bob"
    assert updated.familiarity == 1.0
    assert updated.trust == 1.0
    assert updated.affinity == 1.0
