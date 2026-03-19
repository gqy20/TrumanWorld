import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.api.routes.runs as runs_route
from app.store.models import (
    Agent,
    DirectorMemory,
    Event,
    Location,
    Memory,
    Relationship,
    SimulationRun,
)
from app.store.repositories import DirectorMemoryRepository


class _FakeCognitionRegistry:
    def __init__(self) -> None:
        self.cleaned_runs: list[str] = []

    async def cleanup_run(self, run_id: str) -> int:
        self.cleaned_runs.append(run_id)
        return 1


@pytest.mark.asyncio
async def test_get_world_snapshot_returns_locations_agents_and_public_events(client):
    create_response = await client.post("/api/runs", json={"name": "world-run"})
    run_id = create_response.json()["id"]

    await client.post(f"/api/runs/{run_id}/tick")
    world_response = await client.get(f"/api/runs/{run_id}/world")

    assert world_response.status_code == 200
    body = world_response.json()
    assert body["run"]["id"] == run_id
    assert len(body["locations"]) == 7
    assert any(len(location["occupants"]) >= 1 for location in body["locations"])
    assert len(body["recent_events"]) >= 1
    assert body["director_stats"] == {"total": 0, "executed": 0, "execution_rate": 0}


@pytest.mark.asyncio
async def test_get_world_snapshot_includes_director_stats(client):
    create_response = await client.post("/api/runs", json={"name": "world-director-stats"})
    run_id = create_response.json()["id"]

    inject_response = await client.post(
        f"/api/runs/{run_id}/director/events",
        json={
            "event_type": "broadcast",
            "payload": {"message": "Town hall at plaza"},
            "importance": 0.8,
        },
    )
    world_response = await client.get(f"/api/runs/{run_id}/world")

    assert inject_response.status_code == 200
    assert world_response.status_code == 200
    assert world_response.json()["director_stats"] == {
        "total": 1,
        "executed": 0,
        "execution_rate": 0,
    }


@pytest.mark.asyncio
async def test_get_director_memories_returns_memory_details(client):
    create_response = await client.post("/api/runs", json={"name": "director-memory-list"})
    run_id = create_response.json()["id"]

    inject_response = await client.post(
        f"/api/runs/{run_id}/director/events",
        json={
            "event_type": "broadcast",
            "payload": {"message": "Town hall at plaza"},
            "importance": 0.8,
        },
    )
    memories_response = await client.get(f"/api/runs/{run_id}/director/memories")

    assert inject_response.status_code == 200
    assert memories_response.status_code == 200

    body = memories_response.json()
    assert body["run_id"] == run_id
    assert body["total"] == 1
    assert len(body["memories"]) == 1
    assert body["memories"][0]["scene_goal"] == "gather"
    assert body["memories"][0]["message_hint"] == "Town hall at plaza"
    assert body["memories"][0]["was_executed"] is False
    assert body["memories"][0]["delivery_status"] == "queued"


@pytest.mark.asyncio
async def test_get_director_memories_marks_consumed_and_expired_entries(client, db_session):
    run_id = "00000000-0000-0000-0000-000000000205"
    db_session.add_all(
        [
            SimulationRun(id=run_id, name="director-memory-status", status="running", current_tick=12),
            Agent(id="agent-cast-memory", run_id=run_id, name="Meryl", occupation="resident", personality={}, profile={}, status={}, current_plan={}),
            Agent(id="agent-target-memory", run_id=run_id, name="Truman", occupation="resident", personality={}, profile={}, status={}, current_plan={}),
            Location(id="loc-memory-status", run_id=run_id, name="Plaza", location_type="plaza", capacity=8),
            DirectorMemory(
                id="director-memory-consumed",
                run_id=run_id,
                tick_no=10,
                scene_goal="gather",
                target_cast_ids='["agent-cast-memory"]',
                target_agent_id="agent-target-memory",
                was_executed=True,
                metadata_json={"location_hint": "loc-memory-status"},
            ),
            DirectorMemory(
                id="director-memory-expired",
                run_id=run_id,
                tick_no=1,
                scene_goal="activity",
                target_cast_ids='["agent-cast-memory"]',
                was_executed=False,
                metadata_json={"location_hint": "loc-memory-status"},
            ),
        ]
    )
    await db_session.commit()

    response = await client.get(f"/api/runs/{run_id}/director/memories")

    assert response.status_code == 200
    memories = {memory["id"]: memory for memory in response.json()["memories"]}
    assert memories["director-memory-consumed"]["delivery_status"] == "consumed"
    assert memories["director-memory-consumed"]["target_agent_name"] == "Truman"
    assert memories["director-memory-consumed"]["target_agent_ids"] == ["agent-cast-memory"]
    assert memories["director-memory-consumed"]["target_cast_ids"] == ["agent-cast-memory"]
    assert memories["director-memory-consumed"]["target_agent_names"] == ["Meryl"]
    assert memories["director-memory-consumed"]["target_cast_names"] == ["Meryl"]
    assert memories["director-memory-consumed"]["location_name"] == "Plaza"
    assert memories["director-memory-expired"]["delivery_status"] == "expired"


@pytest.mark.asyncio
async def test_get_director_observation_returns_assessment(client):
    create_response = await client.post("/api/runs", json={"name": "observer-run"})
    run_id = create_response.json()["id"]

    await client.post(f"/api/runs/{run_id}/tick")
    response = await client.get(f"/api/runs/{run_id}/director/observation")

    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == run_id
    assert body["subject_agent_id"]
    assert isinstance(body["subject_alert_score"], float)
    assert body["truman_agent_id"]
    assert body["truman_agent_id"] == body["subject_agent_id"]
    assert body["truman_suspicion_score"] == body["subject_alert_score"]
    assert body["suspicion_level"] in {"low", "guarded", "alerted", "high"}
    assert body["continuity_risk"] in {"stable", "watch", "elevated", "critical"}
    assert isinstance(body["notes"], list)
    assert isinstance(body["focus_agent_ids"], list)


@pytest.mark.asyncio
async def test_director_memory_repository_accepts_generic_target_agent_ids(db_session):
    repo = DirectorMemoryRepository(db_session)

    memory = await repo.create(
        run_id="run-generic-memory",
        tick_no=3,
        scene_goal="gather",
        target_agent_ids=["agent-a", "agent-b"],
        target_agent_id="subject-a",
    )

    assert memory.target_cast_ids == '["agent-a", "agent-b"]'
    assert memory.target_agent_ids == memory.target_cast_ids


@pytest.mark.asyncio
async def test_run_not_found_returns_404(client):
    response = await client.get("/api/runs/00000000-0000-0000-0000-000000000001")

    assert response.status_code == 404
    assert response.json()["detail"] == "Run not found"


@pytest.mark.asyncio
async def test_get_run_events_returns_404_for_missing_run(client):
    response = await client.get("/api/runs/00000000-0000-0000-0000-000000000206/events")

    assert response.status_code == 404
    assert response.json()["detail"] == "Run not found"


@pytest.mark.asyncio
async def test_inject_director_event_rejects_unknown_event_type(client):
    create_response = await client.post("/api/runs", json={"name": "director-run-invalid"})
    run_id = create_response.json()["id"]

    inject_response = await client.post(
        f"/api/runs/{run_id}/director/events",
        json={
            "event_type": "festival",
            "payload": {"message": "Street festival"},
            "importance": 0.8,
        },
    )

    assert inject_response.status_code == 422


@pytest.mark.asyncio
async def test_inject_director_event_rejects_unknown_location_id(client):
    create_response = await client.post("/api/runs", json={"name": "director-run-invalid-location"})
    run_id = create_response.json()["id"]

    inject_response = await client.post(
        f"/api/runs/{run_id}/director/events",
        json={
            "event_type": "shutdown",
            "payload": {"message": "Hospital closed"},
            "location_id": "missing-location",
            "importance": 0.8,
        },
    )

    assert inject_response.status_code == 422
    assert inject_response.json()["detail"] == "Invalid location_id for this run: missing-location"


@pytest.mark.asyncio
async def test_inject_power_outage_persists_world_effect_and_public_timeline_event(
    client, db_session
):
    create_response = await client.post("/api/runs", json={"name": "director-run-power"})
    run_id = create_response.json()["id"]

    square = (
        await db_session.execute(
            select(Location).where(Location.run_id == run_id, Location.location_type == "plaza")
        )
    ).scalar_one()

    inject_response = await client.post(
        f"/api/runs/{run_id}/director/events",
        json={
            "event_type": "power_outage",
            "payload": {"message": "Town square blackout", "duration_ticks": 3},
            "location_id": square.id,
            "importance": 0.9,
        },
    )
    timeline_response = await client.get(f"/api/runs/{run_id}/timeline")
    world_response = await client.get(f"/api/runs/{run_id}/world")

    run = await db_session.get(SimulationRun, run_id)
    world_effects = (run.metadata_json or {}).get("world_effects", {})
    power_outages = world_effects.get("power_outages", [])

    assert inject_response.status_code == 200
    assert inject_response.json()["status"] == "queued"
    assert len(power_outages) == 1
    assert power_outages[0]["location_id"] == square.id
    assert power_outages[0]["message"] == "Town square blackout"

    timeline = timeline_response.json()
    assert any(event["event_type"] == "director_power_outage" for event in timeline["events"])

    world_events = world_response.json()["recent_events"]
    assert any(event["event_type"] == "director_power_outage" for event in world_events)


@pytest.mark.asyncio
async def test_delete_run_removes_related_records_and_cleans_pool(
    client, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    run_id = "00000000-0000-0000-0000-000000000204"
    fake_registry = _FakeCognitionRegistry()
    monkeypatch.setattr(runs_route, "get_cognition_registry", lambda: fake_registry)

    db_session.add_all(
        [
            SimulationRun(id=run_id, name="delete-run", status="running"),
            Agent(id="agent-delete-a", run_id=run_id, name="Alice", occupation="resident", current_location_id="loc-delete", personality={}, profile={}, status={}, current_plan={}),
            Agent(id="agent-delete-b", run_id=run_id, name="Bob", occupation="resident", personality={}, profile={}, status={}, current_plan={}),
            Location(id="loc-delete", run_id=run_id, name="Cafe", location_type="cafe", capacity=4),
            Event(id="event-delete", run_id=run_id, tick_no=1, event_type="talk", actor_agent_id="agent-delete-a", target_agent_id="agent-delete-b", location_id="loc-delete", payload={}),
            Memory(id="memory-delete", run_id=run_id, agent_id="agent-delete-a", tick_no=1, memory_type="episodic_long", memory_category="long_term", content="Talked with Bob", summary="Talked with Bob", importance=0.9, related_agent_id="agent-delete-b", location_id="loc-delete", metadata_json={}),
            Relationship(id="relationship-delete", run_id=run_id, agent_id="agent-delete-a", other_agent_id="agent-delete-b", familiarity=0.3, trust=0.2, affinity=0.4, relation_type="friend"),
            DirectorMemory(id="director-memory-delete", run_id=run_id, tick_no=1, scene_goal="gather", target_cast_ids='["agent-delete-b"]', message_hint="Meet now", was_executed=False),
        ]
    )
    await db_session.commit()

    response = await client.delete(f"/api/runs/{run_id}")

    assert response.status_code == 200
    assert response.json() == {"run_id": run_id, "status": "deleted"}
    assert fake_registry.cleaned_runs == [run_id]
    assert await db_session.get(SimulationRun, run_id) is None
    assert await db_session.get(Agent, "agent-delete-a") is None
    assert await db_session.get(Location, "loc-delete") is None
    assert await db_session.get(Event, "event-delete") is None
    assert await db_session.get(Memory, "memory-delete") is None
    assert await db_session.get(Relationship, "relationship-delete") is None
    assert await db_session.get(DirectorMemory, "director-memory-delete") is None


@pytest.mark.asyncio
async def test_delete_run_returns_404_for_missing_run_and_still_cleans_runtime_resources(
    client, monkeypatch: pytest.MonkeyPatch
):
    fake_registry = _FakeCognitionRegistry()
    monkeypatch.setattr(runs_route, "get_cognition_registry", lambda: fake_registry)

    response = await client.delete("/api/runs/00000000-0000-0000-0000-000000000208")

    assert response.status_code == 404
    assert response.json()["detail"] == "Run not found"
    assert fake_registry.cleaned_runs == ["00000000-0000-0000-0000-000000000208"]
