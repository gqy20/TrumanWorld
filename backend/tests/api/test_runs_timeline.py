import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.store.models import Agent, Event, Location, SimulationRun


@pytest.mark.asyncio
async def test_get_timeline_for_empty_run(client):
    create_response = await client.post(
        "/api/runs", json={"name": "timeline-run", "seed_demo": False}
    )
    run_id = create_response.json()["id"]

    timeline_response = await client.get(f"/api/runs/{run_id}/timeline")

    assert timeline_response.status_code == 200
    data = timeline_response.json()
    assert data["run_id"] == run_id
    assert data["events"] == []
    assert "total" in data
    assert "filtered" in data
    assert "run_info" in data


@pytest.mark.asyncio
async def test_get_timeline_for_empty_run_uses_skipped_world_time(client, db_session: AsyncSession):
    run_id = "00000000-0000-0000-0000-000000000302"
    db_session.add(
        SimulationRun(
            id=run_id,
            name="timeline-empty-clock-run",
            status="running",
            current_tick=288,
            tick_minutes=5,
            metadata_json={"world_start_time": "2026-03-02T06:00:00+00:00"},
        )
    )
    await db_session.commit()

    timeline_response = await client.get(f"/api/runs/{run_id}/timeline")

    assert timeline_response.status_code == 200
    body = timeline_response.json()
    assert body["events"] == []
    assert body["run_info"]["current_tick"] == 288
    assert body["run_info"]["current_world_time_iso"] == "2026-03-03T06:00:00+00:00"


@pytest.mark.asyncio
async def test_get_timeline_resolves_agent_name_and_world_datetime_filters(client, db_session):
    run_id = "00000000-0000-0000-0000-000000000202"
    run = SimulationRun(
        id=run_id,
        name="timeline-filter-run",
        status="running",
        tick_minutes=5,
        metadata_json={"world_start_time": "2026-03-02T07:00:00+00:00"},
    )
    alice = Agent(
        id="agent-alice-filter",
        run_id=run_id,
        name="Alice",
        occupation="resident",
        personality={},
        profile={},
        status={},
        current_plan={},
    )
    bob = Agent(
        id="agent-bob-filter",
        run_id=run_id,
        name="Bob",
        occupation="resident",
        personality={},
        profile={},
        status={},
        current_plan={},
    )
    db_session.add_all(
        [
            run,
            alice,
            bob,
            Event(
                id="timeline-event-1",
                run_id=run_id,
                tick_no=1,
                event_type="talk",
                actor_agent_id=alice.id,
                target_agent_id=bob.id,
                payload={},
            ),
            Event(
                id="timeline-event-2",
                run_id=run_id,
                tick_no=3,
                event_type="move",
                actor_agent_id=bob.id,
                payload={},
            ),
        ]
    )
    await db_session.commit()

    response = await client.get(
        f"/api/runs/{run_id}/timeline",
        params={
            "agent_id": "Alice",
            "world_datetime_from": "2026-03-02T07:05",
            "world_datetime_to": "2026-03-02T07:05",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["filtered"] == 1
    assert [event["id"] for event in body["events"]] == ["timeline-event-1"]
    assert body["events"][0]["payload"]["actor_name"] == "Alice"
    assert body["events"][0]["payload"]["target_name"] == "Bob"
    assert body["events"][0]["world_time"] == "07:05"
    assert body["events"][0]["world_date"] == "2026-03-02"


@pytest.mark.asyncio
async def test_get_timeline_preserves_relationship_impact_payload(client, db_session):
    run_id = "00000000-0000-0000-0000-000000000204"
    run = SimulationRun(
        id=run_id,
        name="timeline-relationship-impact",
        status="running",
        tick_minutes=5,
        metadata_json={"world_start_time": "2026-03-02T07:00:00+00:00"},
    )
    alice = Agent(
        id="agent-alice-impact",
        run_id=run_id,
        name="Alice",
        occupation="resident",
        personality={},
        profile={},
        status={},
        current_plan={},
    )
    bob = Agent(
        id="agent-bob-impact",
        run_id=run_id,
        name="Bob",
        occupation="resident",
        personality={},
        profile={},
        status={},
        current_plan={},
    )
    db_session.add_all(
        [
            run,
            alice,
            bob,
            Event(
                id="timeline-relationship-impact-event",
                run_id=run_id,
                tick_no=1,
                event_type="speech",
                actor_agent_id=alice.id,
                target_agent_id=bob.id,
                payload={
                    "relationship_impact": {
                        "applied": True,
                        "familiarity_delta": 0.1,
                        "trust_delta": 0.01,
                        "affinity_delta": 0.01,
                        "modifiers": ["soft_risk"],
                        "summary": "High-risk social contact reduced trust and affinity gains.",
                    }
                },
            ),
        ]
    )
    await db_session.commit()

    response = await client.get(f"/api/runs/{run_id}/timeline")

    assert response.status_code == 200
    body = response.json()
    assert body["events"][0]["payload"]["actor_name"] == "Alice"
    assert body["events"][0]["payload"]["target_name"] == "Bob"
    assert body["events"][0]["payload"]["relationship_impact"]["summary"] == (
        "High-risk social contact reduced trust and affinity gains."
    )


@pytest.mark.asyncio
async def test_get_run_events_supports_category_filters(client, db_session):
    run_id = "00000000-0000-0000-0000-000000000203"
    db_session.add_all(
        [
            SimulationRun(id=run_id, name="events-run", status="running"),
            Agent(
                id="agent-event-a",
                run_id=run_id,
                name="Alice",
                occupation="resident",
                personality={},
                profile={},
                status={},
                current_plan={},
            ),
            Agent(
                id="agent-event-b",
                run_id=run_id,
                name="Bob",
                occupation="resident",
                personality={},
                profile={},
                status={},
                current_plan={},
            ),
            Location(
                id="loc-event-cafe",
                run_id=run_id,
                name="Cafe",
                location_type="cafe",
                capacity=4,
            ),
            Event(
                id="event-social",
                run_id=run_id,
                tick_no=1,
                event_type="speech",
                actor_agent_id="agent-event-a",
                target_agent_id="agent-event-b",
                payload={},
            ),
            Event(
                id="event-conversation-started",
                run_id=run_id,
                tick_no=1,
                event_type="conversation_started",
                actor_agent_id="agent-event-a",
                target_agent_id="agent-event-b",
                payload={},
            ),
            Event(
                id="event-move",
                run_id=run_id,
                tick_no=2,
                event_type="move",
                actor_agent_id="agent-event-a",
                location_id="loc-event-cafe",
                payload={},
            ),
            Event(
                id="event-rest",
                run_id=run_id,
                tick_no=3,
                event_type="rest",
                actor_agent_id="agent-event-b",
                payload={},
            ),
        ]
    )
    await db_session.commit()

    social = await client.get(f"/api/runs/{run_id}/events", params={"event_type": "social"})
    movement = await client.get(f"/api/runs/{run_id}/events", params={"event_type": "movement"})
    activity = await client.get(f"/api/runs/{run_id}/events", params={"event_type": "activity"})

    assert social.status_code == 200
    assert [event["id"] for event in social.json()["events"]] == [
        "event-social",
        "event-conversation-started",
    ]
    assert movement.status_code == 200
    assert [event["id"] for event in movement.json()["events"]] == ["event-move"]
    assert activity.status_code == 200
    assert [event["id"] for event in activity.json()["events"]] == ["event-rest"]


@pytest.mark.asyncio
async def test_events_incremental_query_with_since_tick(client, db_session):
    create_response = await client.post("/api/runs", json={"name": "incremental-test"})
    run_id = create_response.json()["id"]

    db_session.add_all(
        [
            Event(
                id="inc-event-1",
                run_id=run_id,
                tick_no=1,
                event_type="talk",
                payload={"msg": "tick 1"},
            ),
            Event(
                id="inc-event-2",
                run_id=run_id,
                tick_no=2,
                event_type="move",
                payload={"msg": "tick 2"},
            ),
            Event(
                id="inc-event-3",
                run_id=run_id,
                tick_no=5,
                event_type="talk",
                payload={"msg": "tick 5"},
            ),
            Event(
                id="inc-event-4",
                run_id=run_id,
                tick_no=7,
                event_type="rest",
                payload={"msg": "tick 7"},
            ),
        ]
    )
    await db_session.commit()

    response = await client.get(f"/api/runs/{run_id}/events", params={"since_tick": 2})
    assert response.status_code == 200
    tick_nos = [e["tick_no"] for e in response.json()["events"]]

    assert all(t > 2 for t in tick_nos)
    assert 1 not in tick_nos
    assert 2 not in tick_nos


@pytest.mark.asyncio
async def test_events_incremental_query_returns_latest_tick(client, db_session):
    create_response = await client.post("/api/runs", json={"name": "latest-tick-test"})
    run_id = create_response.json()["id"]

    db_session.add_all(
        [
            Event(id="lt-event-1", run_id=run_id, tick_no=1, event_type="talk", payload={}),
            Event(id="lt-event-2", run_id=run_id, tick_no=5, event_type="move", payload={}),
        ]
    )
    await db_session.commit()

    response = await client.get(f"/api/runs/{run_id}/events")
    assert response.status_code == 200
    data = response.json()

    assert "latest_tick" in data
    assert data["latest_tick"] == 5


@pytest.mark.asyncio
async def test_events_incremental_query_empty_since_tick(client, db_session):
    create_response = await client.post("/api/runs", json={"name": "empty-incremental"})
    run_id = create_response.json()["id"]

    db_session.add_all(
        [
            Event(id="empty-event-1", run_id=run_id, tick_no=1, event_type="talk", payload={}),
            Event(id="empty-event-2", run_id=run_id, tick_no=2, event_type="move", payload={}),
        ]
    )
    await db_session.commit()

    response = await client.get(f"/api/runs/{run_id}/events", params={"since_tick": 100})
    assert response.status_code == 200
    data = response.json()

    assert len(data["events"]) == 0
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_inject_director_event_persists_to_timeline(client):
    create_response = await client.post("/api/runs", json={"name": "director-run"})
    run_id = create_response.json()["id"]

    inject_response = await client.post(
        f"/api/runs/{run_id}/director/events",
        json={
            "event_type": "broadcast",
            "payload": {"message": "Town hall at plaza"},
            "importance": 0.8,
        },
    )
    timeline_response = await client.get(f"/api/runs/{run_id}/timeline")

    assert inject_response.status_code == 200
    assert inject_response.json()["status"] == "queued"

    timeline = timeline_response.json()
    assert len(timeline["events"]) == 1
    assert timeline["events"][0]["event_type"] == "director_broadcast"
    assert timeline["events"][0]["payload"]["message"] == "Town hall at plaza"


@pytest.mark.asyncio
async def test_get_timeline_supports_order_desc_and_event_type_filter(client, db_session):
    run_id = "00000000-0000-0000-0000-000000000207"
    db_session.add_all(
        [
            SimulationRun(id=run_id, name="timeline-order-run", status="running"),
            Event(
                id="timeline-order-talk", run_id=run_id, tick_no=2, event_type="talk", payload={}
            ),
            Event(
                id="timeline-order-move", run_id=run_id, tick_no=5, event_type="move", payload={}
            ),
        ]
    )
    await db_session.commit()

    response = await client.get(
        f"/api/runs/{run_id}/timeline",
        params={"event_type": "move", "order_desc": "true"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["filtered"] == 1
    assert [event["id"] for event in body["events"]] == ["timeline-order-move"]
