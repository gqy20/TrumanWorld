import pytest

from app.sim.action_resolver import ActionIntent
from app.sim.service import SimulationService
from app.store.models import Agent, Event, Location, Memory, Relationship, SimulationRun


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
        event_type="speech",
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
    assert body["recent_events"][0]["event_type"] == "speech"
    assert len(body["memories"]) == 1
    assert body["memories"][0]["summary"] == "Met Bob"
    assert body["memories"][0]["memory_category"] == "short_term"
    assert body["memories"][0]["event_importance"] == 0.0
    assert len(body["relationships"]) == 1
    assert body["relationships"][0]["other_agent_id"] == "bob"


@pytest.mark.asyncio
async def test_list_agents_returns_run_agents(client, db_session):
    run_id = "00000000-0000-0000-0000-000000000104"
    run = SimulationRun(id=run_id, name="demo", status="running")
    alice = Agent(
        id="alice-list",
        run_id=run_id,
        name="Alice",
        occupation="barista",
        current_goal="work",
        personality={},
        profile={},
        status={},
        current_plan={},
    )
    bob = Agent(
        id="bob-list",
        run_id=run_id,
        name="Bob",
        occupation="resident",
        current_goal="rest",
        personality={},
        profile={},
        status={},
        current_plan={},
    )

    db_session.add_all([run, alice, bob])
    await db_session.commit()

    response = await client.get(f"/api/runs/{run_id}/agents")

    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == run_id
    assert [agent["id"] for agent in body["agents"]] == ["alice-list", "bob-list"]


@pytest.mark.asyncio
async def test_list_agents_returns_404_when_run_missing(client):
    response = await client.get("/api/runs/00000000-0000-0000-0000-000000000999/agents")

    assert response.status_code == 404
    assert response.json()["detail"] == "Run not found"


@pytest.mark.asyncio
async def test_get_agent_returns_generated_tick_memories(client, db_session):
    run_id = "00000000-0000-0000-0000-000000000103"
    run = SimulationRun(id=run_id, name="demo", status="running", current_tick=0, tick_minutes=5)
    home = Location(id="loc-home", run_id=run_id, name="Home", location_type="home", capacity=2)
    park = Location(id="loc-park", run_id=run_id, name="Park", location_type="park", capacity=2)
    agent = Agent(
        id="alice",
        run_id=run_id,
        name="Alice",
        occupation="resident",
        home_location_id="loc-home",
        current_location_id="loc-home",
        current_goal="move:loc-park",
        personality={},
        profile={},
        status={},
        current_plan={},
    )
    db_session.add_all([run, home, park, agent])
    await db_session.commit()

    await SimulationService(db_session).run_tick(
        run_id,
        [ActionIntent(agent_id="alice", action_type="move", target_location_id="loc-park")],
    )

    response = await client.get(f"/api/runs/{run_id}/agents/alice")

    assert response.status_code == 200
    body = response.json()
    assert len(body["recent_events"]) == 1
    assert body["recent_events"][0]["event_type"] == "move"
    assert len(body["memories"]) == 1
    # 记忆摘要使用地点名称而非 ID
    assert body["memories"][0]["summary"] == "Moved to Park"
    assert body["memories"][0]["memory_category"] == "short_term"


@pytest.mark.asyncio
async def test_get_agent_returns_generated_talk_memory_for_target(client, db_session):
    run_id = "00000000-0000-0000-0000-000000000105"
    run = SimulationRun(id=run_id, name="demo", status="running", current_tick=0, tick_minutes=5)
    cafe = Location(id="loc-cafe", run_id=run_id, name="Cafe", location_type="cafe", capacity=4)
    alice = Agent(
        id="alice-talk",
        run_id=run_id,
        name="Alice",
        occupation="resident",
        home_location_id="loc-cafe",
        current_location_id="loc-cafe",
        personality={},
        profile={},
        status={},
        current_plan={},
    )
    bob = Agent(
        id="bob-talk",
        run_id=run_id,
        name="Bob",
        occupation="resident",
        home_location_id="loc-cafe",
        current_location_id="loc-cafe",
        personality={},
        profile={},
        status={},
        current_plan={},
    )
    db_session.add_all([run, cafe, alice, bob])
    await db_session.commit()

    await SimulationService(db_session).run_tick(
        run_id,
        [ActionIntent(agent_id="alice-talk", action_type="talk", target_agent_id="bob-talk")],
    )

    response = await client.get(f"/api/runs/{run_id}/agents/bob-talk")

    assert response.status_code == 200
    body = response.json()
    assert len(body["recent_events"]) == 3
    assert {event["event_type"] for event in body["recent_events"]} == {
        "conversation_started",
        "speech",
        "listen",
    }
    assert len(body["memories"]) == 1
    assert body["memories"][0]["summary"].startswith("Talked with Alice")
    assert body["memories"][0]["self_relevance"] >= 0.8


@pytest.mark.asyncio
async def test_get_agent_returns_404_when_agent_missing(client, db_session):
    run_id = "00000000-0000-0000-0000-000000000102"
    run = SimulationRun(id=run_id, name="demo", status="running")
    db_session.add(run)
    await db_session.commit()

    response = await client.get(f"/api/runs/{run_id}/agents/missing-agent")

    assert response.status_code == 404
    assert response.json()["detail"] == "Agent not found"


@pytest.mark.asyncio
async def test_get_agent_returns_404_when_agent_belongs_to_other_run(client, db_session):
    run_id = "00000000-0000-0000-0000-000000000106"
    other_run_id = "00000000-0000-0000-0000-000000000107"
    db_session.add_all(
        [
            SimulationRun(id=run_id, name="demo-a", status="running"),
            SimulationRun(id=other_run_id, name="demo-b", status="running"),
            Agent(
                id="cross-run-agent",
                run_id=other_run_id,
                name="Alice",
                occupation="resident",
                personality={},
                profile={},
                status={},
                current_plan={},
            ),
        ]
    )
    await db_session.commit()

    response = await client.get(f"/api/runs/{run_id}/agents/cross-run-agent")

    assert response.status_code == 404
    assert response.json()["detail"] == "Agent not found"
