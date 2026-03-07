import pytest

from app.store.models import Agent, Event, Memory, Relationship, SimulationRun


@pytest.mark.asyncio
async def test_get_agent_returns_state_and_related_data(client, db_session):
    run_id = "00000000-0000-0000-0000-000000000101"
    run = SimulationRun(id=run_id, name="demo", status="running")
    agent = Agent(
        id="alice",
        run_id=run_id,
        name="Alice",
        occupation="barista",
        current_goal="open cafe",
        personality={"openness": 0.7},
        profile={"bio": "demo"},
        status={"energy": 0.8},
        current_plan={"morning": "work"},
    )
    event = Event(
        id="event-1",
        run_id=run_id,
        tick_no=3,
        event_type="talk",
        actor_agent_id="alice",
        payload={"message": "hello"},
    )
    memory = Memory(
        id="memory-1",
        run_id=run_id,
        agent_id="alice",
        memory_type="episodic",
        content="Met Bob at the cafe.",
        summary="Met Bob",
        importance=0.6,
        metadata_json={},
    )
    relationship = Relationship(
        id="rel-1",
        run_id=run_id,
        agent_id="alice",
        other_agent_id="bob",
        familiarity=0.4,
        trust=0.2,
        affinity=0.3,
        relation_type="acquaintance",
    )

    db_session.add_all([run, agent, event, memory, relationship])
    await db_session.commit()

    response = await client.get(f"/api/runs/{run_id}/agents/alice")

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Alice"
    assert body["occupation"] == "barista"
    assert body["current_goal"] == "open cafe"
    assert len(body["recent_events"]) == 1
    assert body["recent_events"][0]["event_type"] == "talk"
    assert len(body["memories"]) == 1
    assert body["memories"][0]["summary"] == "Met Bob"
    assert len(body["relationships"]) == 1
    assert body["relationships"][0]["other_agent_id"] == "bob"


@pytest.mark.asyncio
async def test_get_agent_returns_404_when_agent_missing(client, db_session):
    run_id = "00000000-0000-0000-0000-000000000102"
    run = SimulationRun(id=run_id, name="demo", status="running")
    db_session.add(run)
    await db_session.commit()

    response = await client.get(f"/api/runs/{run_id}/agents/missing-agent")

    assert response.status_code == 404
    assert response.json()["detail"] == "Agent not found"
