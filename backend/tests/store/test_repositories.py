import pytest

from app.store.models import Agent, Event, SimulationRun
from app.store.repositories import AgentRepository, EventRepository, RelationshipRepository, RunRepository


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


@pytest.mark.asyncio
async def test_list_recent_events_prioritises_talk_and_move_over_work_rest(db_session):
    """talk/move events must be returned before work/rest events even when the
    work/rest events occurred in more recent ticks, so that LLM context windows
    are not dominated by repetitive noise."""
    run = SimulationRun(id="run-priority", name="priority", status="running")
    agent = Agent(
        id="agent-p",
        run_id="run-priority",
        name="Alpha",
        occupation="tester",
        personality={},
        profile={},
        status={},
        current_plan={},
    )
    db_session.add_all([run, agent])

    # Two work events at high ticks, one talk event at a low tick
    db_session.add_all([
        Event(
            id="ev-work-10", run_id="run-priority", tick_no=10,
            event_type="work",
            actor_agent_id="agent-p",
            payload={"agent_id": "agent-p"},
        ),
        Event(
            id="ev-work-11", run_id="run-priority", tick_no=11,
            event_type="work",
            actor_agent_id="agent-p",
            payload={"agent_id": "agent-p"},
        ),
        Event(
            id="ev-talk-5", run_id="run-priority", tick_no=5,
            event_type="talk",
            actor_agent_id="agent-p",
            payload={"agent_id": "agent-p", "message": "hello"},
        ),
        Event(
            id="ev-move-3", run_id="run-priority", tick_no=3,
            event_type="move",
            actor_agent_id="agent-p",
            payload={"agent_id": "agent-p"},
        ),
    ])
    await db_session.commit()

    repo = AgentRepository(db_session)
    events = await repo.list_recent_events("run-priority", "agent-p", limit=4)
    event_types = [e.event_type for e in events]

    # talk and move must appear before work entries
    assert event_types.index("talk") < event_types.index("work")
    assert event_types.index("move") < event_types.index("work")
    # Both talk and the two work events should all be present within limit=4
    assert "talk" in event_types
    assert "move" in event_types
    assert event_types.count("work") == 2
