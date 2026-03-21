import pytest

from app.sim.action_resolver import ActionIntent
from app.sim.service import SimulationService
from app.store.models import Agent, Event, GovernanceRecord, Location, Memory, Relationship, SimulationRun


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
async def test_get_agent_returns_world_rules_summary(client, db_session):
    run_id = "00000000-0000-0000-0000-000000000110"
    run = SimulationRun(
        id=run_id,
        name="demo",
        status="running",
        current_tick=1,
        tick_minutes=5,
        metadata_json={
            "world_effects": {
                "location_shutdowns": [
                    {
                        "location_id": "loc-cafe-summary",
                        "start_tick": 0,
                        "end_tick": 4,
                        "message": "Cafe temporarily closed",
                    }
                ]
            }
        },
    )
    cafe = Location(
        id="loc-cafe-summary",
        run_id=run_id,
        name="Cafe",
        location_type="cafe",
        capacity=4,
    )
    alice = Agent(
        id="alice-summary",
        run_id=run_id,
        name="Alice",
        occupation="barista",
        current_goal="talk",
        current_location_id="loc-cafe-summary",
        home_location_id="loc-home-summary",
        personality={},
        profile={"workplace_location_id": "loc-cafe-summary"},
        status={"energy": 0.8},
        current_plan={},
    )
    bob = Agent(
        id="bob-summary",
        run_id=run_id,
        name="Bob",
        occupation="resident",
        current_location_id="loc-cafe-summary",
        home_location_id="loc-home-summary",
        personality={},
        profile={},
        status={},
        current_plan={},
    )

    db_session.add_all([run, cafe, alice, bob])
    await db_session.commit()

    response = await client.get(f"/api/runs/{run_id}/agents/alice-summary")

    assert response.status_code == 200
    body = response.json()
    assert body["world_rules_summary"]["available_actions"] == ["move", "rest"]
    assert body["world_rules_summary"]["policy_notices"] == ["Cafe temporarily closed"]


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
    assert response.json() == {
        "detail": "Run not found",
        "code": "RUN_NOT_FOUND",
        "context": {"run_id": "00000000-0000-0000-0000-000000000999"},
    }


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
    assert response.json() == {
        "detail": "Agent not found",
        "code": "AGENT_NOT_FOUND",
        "context": {"run_id": run_id, "agent_id": "missing-agent"},
    }


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
    assert response.json() == {
        "detail": "Agent not found",
        "code": "AGENT_NOT_FOUND",
        "context": {"run_id": run_id, "agent_id": "cross-run-agent"},
    }


@pytest.mark.asyncio
async def test_get_agent_filters_recent_events_and_memories(client, db_session):
    run_id = "00000000-0000-0000-0000-000000000108"
    run = SimulationRun(id=run_id, name="demo", status="running")
    alice = Agent(
        id="alice-filter",
        run_id=run_id,
        name="Alice",
        occupation="resident",
        current_location_id="loc-cafe",
        personality={},
        profile={},
        status={},
        current_plan={},
    )
    bob = Agent(
        id="bob-filter",
        run_id=run_id,
        name="Bob",
        occupation="resident",
        personality={},
        profile={},
        status={},
        current_plan={},
    )
    cafe = Location(id="loc-cafe", run_id=run_id, name="Cafe", location_type="cafe", capacity=4)
    events = [
        Event(
            id="event-filter-speech",
            run_id=run_id,
            tick_no=8,
            event_type="speech",
            actor_agent_id="alice-filter",
            target_agent_id="bob-filter",
            location_id="loc-cafe",
            payload={"message": "Secret meeting tonight"},
        ),
        Event(
            id="event-filter-move",
            run_id=run_id,
            tick_no=7,
            event_type="move",
            actor_agent_id="alice-filter",
            location_id="loc-cafe",
            payload={"reason": "Headed to the cafe"},
        ),
        Event(
            id="event-filter-work",
            run_id=run_id,
            tick_no=6,
            event_type="work",
            actor_agent_id="alice-filter",
            location_id="loc-cafe",
            payload={},
        ),
    ]
    memories = [
        Memory(
            id="memory-filter-secret",
            run_id=run_id,
            agent_id="alice-filter",
            tick_no=8,
            memory_type="episodic",
            memory_category="long_term",
            summary="Secret plan",
            content="Remembered the secret meeting with Bob.",
            importance=0.9,
            related_agent_id="bob-filter",
            metadata_json={},
        ),
        Memory(
            id="memory-filter-routine",
            run_id=run_id,
            agent_id="alice-filter",
            tick_no=7,
            memory_type="episodic_short",
            memory_category="short_term",
            summary="Worked",
            content="Worked during this tick.",
            importance=0.1,
            metadata_json={"event_type": "work"},
        ),
    ]

    db_session.add_all([run, cafe, alice, bob, *events, *memories])
    await db_session.commit()

    response = await client.get(
        f"/api/runs/{run_id}/agents/alice-filter",
        params={
            "event_type": "speech",
            "event_query": "secret",
            "include_routine_events": "false",
            "memory_category": "long_term",
            "memory_query": "secret",
            "min_memory_importance": "0.8",
            "related_agent_id": "bob-filter",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert [event["id"] for event in body["recent_events"]] == ["event-filter-speech"]
    assert [memory["id"] for memory in body["memories"]] == ["memory-filter-secret"]


@pytest.mark.asyncio
async def test_get_agent_filters_by_limits_and_memory_type(client, db_session):
    run_id = "00000000-0000-0000-0000-000000000109"
    run = SimulationRun(id=run_id, name="demo", status="running")
    agent = Agent(
        id="alice-limit",
        run_id=run_id,
        name="Alice",
        occupation="resident",
        personality={},
        profile={},
        status={},
        current_plan={},
    )
    events = [
        Event(
            id="event-limit-new",
            run_id=run_id,
            tick_no=9,
            event_type="speech",
            actor_agent_id="alice-limit",
            payload={"message": "newest"},
        ),
        Event(
            id="event-limit-old",
            run_id=run_id,
            tick_no=8,
            event_type="speech",
            actor_agent_id="alice-limit",
            payload={"message": "older"},
        ),
    ]
    memories = [
        Memory(
            id="memory-limit-episodic",
            run_id=run_id,
            agent_id="alice-limit",
            tick_no=9,
            memory_type="episodic",
            memory_category="medium_term",
            summary="Conversation",
            content="Important conversation.",
            importance=0.8,
            metadata_json={},
        ),
        Memory(
            id="memory-limit-reflection",
            run_id=run_id,
            agent_id="alice-limit",
            tick_no=8,
            memory_type="reflection",
            memory_category="long_term",
            summary="Reflection",
            content="Reflected on the day.",
            importance=0.7,
            metadata_json={},
        ),
    ]

    db_session.add_all([run, agent, *events, *memories])
    await db_session.commit()

    response = await client.get(
        f"/api/runs/{run_id}/agents/alice-limit",
        params={
            "event_limit": "1",
            "memory_limit": "1",
            "memory_type": "reflection",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert [event["id"] for event in body["recent_events"]] == ["event-limit-new"]
    assert [memory["id"] for memory in body["memories"]] == ["memory-limit-reflection"]


@pytest.mark.asyncio
async def test_get_agent_governance_records_returns_ledger_entries(client, db_session):
    run_id = "00000000-0000-0000-0000-000000000111"
    run = SimulationRun(id=run_id, name="demo", status="running")
    cafe = Location(id="loc-cafe-ledger", run_id=run_id, name="Cafe", location_type="cafe", capacity=4)
    agent = Agent(
        id="alice-ledger",
        run_id=run_id,
        name="Alice",
        occupation="resident",
        personality={},
        profile={},
        status={},
        current_plan={},
    )
    event = Event(
        id="event-ledger-1",
        run_id=run_id,
        tick_no=5,
        event_type="talk",
        actor_agent_id="alice-ledger",
        location_id="loc-cafe-ledger",
        payload={"message": "forbidden topic"},
    )
    record_newer = GovernanceRecord(
        id="gov-ledger-2",
        run_id=run_id,
        agent_id="alice-ledger",
        tick_no=6,
        source_event_id="event-ledger-1",
        location_id="loc-cafe-ledger",
        action_type="talk",
        decision="warn",
        reason="Escalated after repeated surveillance hits",
        observed=True,
        observation_score=0.72,
        intervention_score=0.81,
        metadata_json={"rule_id": "policy.repeat-surveillance", "warning_count": 2},
    )
    record_older = GovernanceRecord(
        id="gov-ledger-1",
        run_id=run_id,
        agent_id="alice-ledger",
        tick_no=4,
        source_event_id="event-ledger-1",
        location_id="loc-cafe-ledger",
        action_type="talk",
        decision="record_only",
        reason="Low-confidence observation only",
        observed=True,
        observation_score=0.41,
        intervention_score=0.22,
        metadata_json={"rule_id": "policy.surveillance", "observation_count": 1},
    )

    db_session.add_all([run, cafe, agent, event, record_newer, record_older])
    await db_session.commit()

    response = await client.get(
        f"/api/runs/{run_id}/agents/alice-ledger/governance-records",
        params={"limit": "1"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == run_id
    assert body["agent_id"] == "alice-ledger"
    assert body["total"] == 1
    assert [record["id"] for record in body["records"]] == ["gov-ledger-2"]
    assert body["records"][0] == {
        "id": "gov-ledger-2",
        "tick_no": 6,
        "source_event_id": "event-ledger-1",
        "location_id": "loc-cafe-ledger",
        "location_name": "Cafe",
        "action_type": "talk",
        "decision": "warn",
        "reason": "Escalated after repeated surveillance hits",
        "observed": True,
        "observation_score": 0.72,
        "intervention_score": 0.81,
        "metadata": {"rule_id": "policy.repeat-surveillance", "warning_count": 2},
    }


@pytest.mark.asyncio
async def test_get_agent_governance_records_returns_404_when_agent_missing(client, db_session):
    run_id = "00000000-0000-0000-0000-000000000112"
    db_session.add(SimulationRun(id=run_id, name="demo", status="running"))
    await db_session.commit()

    response = await client.get(f"/api/runs/{run_id}/agents/missing/governance-records")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Agent not found",
        "code": "AGENT_NOT_FOUND",
        "context": {"run_id": run_id, "agent_id": "missing"},
    }
