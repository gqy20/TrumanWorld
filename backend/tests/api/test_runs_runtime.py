import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.api.routes.runs as runs_route
from app.store.models import (
    Agent,
    AgentEconomicState,
    DirectorDirective,
    DirectorMemory,
    EconomicEffectLog,
    Event,
    GovernanceCase,
    GovernanceRecord,
    GovernanceRestriction,
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
async def test_get_world_snapshot_returns_locations_agents_and_public_events(client, db_session):
    create_response = await client.post("/api/runs", json={"name": "world-run"})
    run_id = create_response.json()["id"]

    db_session.add(
        Event(
            id="world-snapshot-public-event",
            run_id=run_id,
            tick_no=1,
            event_type="rest",
            visibility="public",
            payload={},
        )
    )
    await db_session.commit()
    world_response = await client.get(f"/api/runs/{run_id}/world")

    assert world_response.status_code == 200
    body = world_response.json()
    assert body["run"]["id"] == run_id
    assert body["subject_agent_id"]
    assert len(body["locations"]) == 7
    assert body["navigation"]["version"] == 1
    assert body["navigation"]["nodes"]
    assert body["navigation"]["edges"]
    assert set(body["navigation"]["location_entrances"]) == {
        location["id"] for location in body["locations"]
    }
    assert any(len(location["occupants"]) >= 1 for location in body["locations"])
    occupant = next(
        occupant for location in body["locations"] for occupant in location["occupants"]
    )
    assert isinstance(occupant["status"], dict)
    assert isinstance(occupant["profile"], dict)
    assert len(body["recent_events"]) >= 1
    assert body["director_stats"] == {"total": 0, "executed": 0, "execution_rate": 0}


@pytest.mark.asyncio
async def test_get_world_snapshot_keeps_in_transit_agent_outside_location_occupants(
    client,
    db_session,
):
    run_id = "00000000-0000-0000-0000-000000000208"
    home_id = "transit-home"
    cafe_id = "transit-cafe"
    agent_id = "transit-alice"
    db_session.add_all(
        [
            SimulationRun(
                id=run_id,
                name="world-transit",
                status="running",
                current_tick=3,
            ),
            Location(
                id=home_id,
                run_id=run_id,
                name="Home",
                location_type="home",
                capacity=4,
            ),
            Location(
                id=cafe_id,
                run_id=run_id,
                name="Cafe",
                location_type="cafe",
                capacity=4,
            ),
            Agent(
                id=agent_id,
                run_id=run_id,
                name="Alice",
                occupation="resident",
                home_location_id=home_id,
                current_location_id=home_id,
                personality={},
                profile={},
                status={},
                current_plan={},
                movement={
                    "id": "movement-alice-cafe",
                    "state": "in_transit",
                    "from_location_id": home_id,
                    "to_location_id": cafe_id,
                    "started_tick": 2,
                    "arrival_tick": 4,
                },
            ),
        ]
    )
    await db_session.commit()

    response = await client.get(f"/api/runs/{run_id}/world")

    assert response.status_code == 200
    body = response.json()
    alice = next(agent for agent in body["agents"] if agent["id"] == agent_id)
    assert alice["current_location_id"] is None
    assert alice["movement"] == {
        "id": "movement-alice-cafe",
        "state": "in_transit",
        "from_location_id": home_id,
        "to_location_id": cafe_id,
        "started_tick": 2,
        "arrival_tick": 4,
        "route_node_ids": [],
        "distance": 0.0,
        "speed": 1.5,
    }
    assert all(
        occupant["id"] != agent_id
        for location in body["locations"]
        for occupant in location["occupants"]
    )


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
            SimulationRun(
                id=run_id, name="director-memory-status", status="running", current_tick=12
            ),
            Agent(
                id="agent-cast-memory",
                run_id=run_id,
                name="Meryl",
                occupation="resident",
                personality={},
                profile={},
                status={},
                current_plan={},
            ),
            Agent(
                id="agent-target-memory",
                run_id=run_id,
                name="Truman",
                occupation="resident",
                personality={},
                profile={},
                status={},
                current_plan={},
            ),
            Location(
                id="loc-memory-status",
                run_id=run_id,
                name="Plaza",
                location_type="plaza",
                capacity=8,
            ),
            DirectorMemory(
                id="director-memory-consumed",
                run_id=run_id,
                tick_no=10,
                scene_goal="gather",
                target_agent_ids='["agent-cast-memory"]',
                target_agent_id="agent-target-memory",
                trigger_subject_alert_score=0.7,
                was_executed=True,
                metadata_json={"location_hint": "loc-memory-status"},
            ),
            DirectorMemory(
                id="director-memory-expired",
                run_id=run_id,
                tick_no=1,
                scene_goal="activity",
                target_agent_ids='["agent-cast-memory"]',
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
    assert memories["director-memory-consumed"]["target_agent_names"] == ["Meryl"]
    assert memories["director-memory-consumed"]["trigger_subject_alert_score"] == 0.7
    assert "target_cast_ids" not in memories["director-memory-consumed"]
    assert "target_cast_names" not in memories["director-memory-consumed"]
    assert "trigger_suspicion_score" not in memories["director-memory-consumed"]
    assert memories["director-memory-consumed"]["location_name"] == "Plaza"
    assert memories["director-memory-expired"]["delivery_status"] == "expired"


@pytest.mark.asyncio
async def test_get_director_directives_supports_status_and_detail(client, db_session):
    run_id = "00000000-0000-0000-0000-000000000211"
    db_session.add_all(
        [
            SimulationRun(id=run_id, name="directive-api", status="running", current_tick=4),
            Agent(
                id="directive-cast",
                run_id=run_id,
                name="Meryl",
                personality={},
                profile={},
                status={},
                current_plan={},
            ),
            Agent(
                id="directive-subject",
                run_id=run_id,
                name="Truman",
                personality={},
                profile={},
                status={},
                current_plan={},
            ),
            Location(
                id="directive-plaza",
                run_id=run_id,
                name="Plaza",
                location_type="plaza",
            ),
            DirectorDirective(
                id="directive-active-1",
                run_id=run_id,
                target_agent_id="directive-cast",
                subject_agent_id="directive-subject",
                objective="soft_check_in",
                mode="priority",
                priority="high",
                status="active",
                issued_tick=3,
                expires_at_tick=7,
                location_id="directive-plaza",
                constraints_json={"target_agent_id": "directive-subject"},
                completion_criteria_json={"action_type": "talk"},
                source="auto",
            ),
        ]
    )
    await db_session.commit()

    list_response = await client.get(
        f"/api/runs/{run_id}/director/directives", params={"status": "active"}
    )
    detail_response = await client.get(f"/api/runs/{run_id}/director/directives/directive-active-1")

    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1
    item = list_response.json()["directives"][0]
    assert item["target_agent_name"] == "Meryl"
    assert item["subject_agent_name"] == "Truman"
    assert item["location_name"] == "Plaza"
    assert item["attempt_count"] == 0
    assert item["source_memory_id"] is None
    assert detail_response.status_code == 200
    assert detail_response.json()["completion_criteria"] == {"action_type": "talk"}


@pytest.mark.asyncio
async def test_get_director_directive_returns_404_for_another_run(client):
    create_response = await client.post("/api/runs", json={"name": "directive-not-found"})
    run_id = create_response.json()["id"]

    response = await client.get(f"/api/runs/{run_id}/director/directives/missing")

    assert response.status_code == 404
    assert response.json()["code"] == "DIRECTOR_DIRECTIVE_NOT_FOUND"


@pytest.mark.asyncio
async def test_get_director_governance_records_returns_filtered_ledger(client, db_session):
    run_id = "00000000-0000-0000-0000-000000000206"
    db_session.add_all(
        [
            SimulationRun(id=run_id, name="director-governance-ledger", status="running"),
            Agent(
                id="agent-governance-alice",
                run_id=run_id,
                name="Alice",
                occupation="resident",
                personality={},
                profile={},
                status={},
                current_plan={},
            ),
            Agent(
                id="agent-governance-bob",
                run_id=run_id,
                name="Bob",
                occupation="resident",
                personality={},
                profile={},
                status={},
                current_plan={},
            ),
            Location(
                id="loc-governance-plaza",
                run_id=run_id,
                name="Plaza",
                location_type="plaza",
                capacity=8,
            ),
            GovernanceRecord(
                id="gov-director-warn",
                run_id=run_id,
                agent_id="agent-governance-alice",
                tick_no=9,
                source_event_id=None,
                location_id="loc-governance-plaza",
                action_type="talk",
                decision="warn",
                reason="Repeated monitored speech",
                observed=True,
                observation_score=0.77,
                intervention_score=0.84,
                metadata_json={"matched_signals": ["social"], "enforcement_action": "warning"},
            ),
            GovernanceRecord(
                id="gov-director-record",
                run_id=run_id,
                agent_id="agent-governance-bob",
                tick_no=8,
                source_event_id=None,
                location_id="loc-governance-plaza",
                action_type="move",
                decision="record_only",
                reason="Suspicious route only",
                observed=True,
                observation_score=0.51,
                intervention_score=0.3,
                metadata_json={"matched_signals": ["sensitive_location"]},
            ),
        ]
    )
    await db_session.commit()

    response = await client.get(
        f"/api/runs/{run_id}/director/governance-records",
        params={"decision": "warn", "agent_id": "agent-governance-alice", "limit": "10"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == run_id
    assert body["total"] == 1
    assert body["records"][0] == {
        "id": "gov-director-warn",
        "tick_no": 9,
        "source_event_id": None,
        "agent_id": "agent-governance-alice",
        "agent_name": "Alice",
        "location_id": "loc-governance-plaza",
        "location_name": "Plaza",
        "action_type": "talk",
        "decision": "warn",
        "reason": "Repeated monitored speech",
        "observed": True,
        "observation_score": 0.77,
        "intervention_score": 0.84,
        "metadata": {"matched_signals": ["social"], "enforcement_action": "warning"},
    }


@pytest.mark.asyncio
async def test_get_director_governance_records_returns_404_when_run_missing(client):
    response = await client.get(
        "/api/runs/00000000-0000-0000-0000-000000000299/director/governance-records"
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_director_observation_returns_assessment(client):
    create_response = await client.post("/api/runs", json={"name": "observer-run"})
    run_id = create_response.json()["id"]

    response = await client.get(f"/api/runs/{run_id}/director/observation")

    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == run_id
    assert body["subject_agent_id"]
    assert body["subject_alert_tracking_enabled"] is True
    assert isinstance(body["subject_alert_score"], float)
    assert "truman_agent_id" not in body
    assert "truman_suspicion_score" not in body
    assert body["suspicion_level"] in {"low", "guarded", "alerted", "high"}
    assert body["continuity_risk"] in {"stable", "watch", "elevated", "critical"}
    assert isinstance(body["notes"], list)
    assert isinstance(body["focus_agent_ids"], list)


@pytest.mark.asyncio
async def test_get_director_observation_returns_null_alert_score_when_tracking_disabled(
    client, monkeypatch: pytest.MonkeyPatch
):
    import app.api.routes.run_director as run_director_module
    from app.director.observer import DirectorAssessment

    create_response = await client.post(
        "/api/runs",
        json={"name": "observer-run-no-alert", "scenario_type": "open_world"},
    )
    run_id = create_response.json()["id"]

    async def _fake_observe_run(self, run_id: str):
        return DirectorAssessment(
            run_id=run_id,
            current_tick=3,
            subject_agent_id="subject-1",
            subject_alert_score=0.0,
            subject_alert_tracking_enabled=False,
            suspicion_level="low",
            continuity_risk="watch",
            focus_agent_ids=["subject-1"],
            notes=["Open world does not use subject alert tracking."],
        )

    monkeypatch.setattr(run_director_module.SimulationService, "observe_run", _fake_observe_run)

    response = await client.get(f"/api/runs/{run_id}/director/observation")

    assert response.status_code == 200
    body = response.json()
    assert body["subject_alert_tracking_enabled"] is False
    assert body["subject_alert_score"] is None
    assert body["continuity_risk"] == "watch"


@pytest.mark.asyncio
async def test_director_memory_repository_accepts_generic_target_agent_ids(db_session):
    repo = DirectorMemoryRepository(db_session)

    memory = await repo.create(
        run_id="run-generic-memory",
        tick_no=3,
        scene_goal="gather",
        target_agent_ids=["agent-a", "agent-b"],
        target_agent_id="subject-a",
        trigger_subject_alert_score=0.4,
    )

    assert memory.target_agent_ids == '["agent-a", "agent-b"]'
    assert memory.trigger_subject_alert_score == 0.4


@pytest.mark.asyncio
async def test_director_memory_repository_returns_latest_subject_alert_score(db_session):
    repo = DirectorMemoryRepository(db_session)

    await repo.create(
        run_id="run-alert-alias",
        tick_no=4,
        scene_goal="observe",
        trigger_subject_alert_score=0.55,
    )

    latest_alert = await repo.get_latest_subject_alert_score("run-alert-alias")
    assert latest_alert == 0.55


@pytest.mark.asyncio
async def test_run_not_found_returns_404(client):
    response = await client.get("/api/runs/00000000-0000-0000-0000-000000000001")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Run not found",
        "code": "RUN_NOT_FOUND",
        "context": {"run_id": "00000000-0000-0000-0000-000000000001"},
    }


@pytest.mark.asyncio
async def test_get_run_events_returns_404_for_missing_run(client):
    response = await client.get("/api/runs/00000000-0000-0000-0000-000000000206/events")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Run not found",
        "code": "RUN_NOT_FOUND",
        "context": {"run_id": "00000000-0000-0000-0000-000000000206"},
    }


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
    assert inject_response.json() == {
        "detail": "Invalid location_id for this run: missing-location",
        "code": "DIRECTOR_EVENT_INVALID",
        "context": {"run_id": run_id, "event_type": "shutdown"},
    }


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
async def test_inject_shutdown_persists_location_shutdown_effect(client, db_session):
    create_response = await client.post("/api/runs", json={"name": "director-run-shutdown"})
    run_id = create_response.json()["id"]

    square = (
        await db_session.execute(
            select(Location).where(Location.run_id == run_id, Location.location_type == "plaza")
        )
    ).scalar_one()

    inject_response = await client.post(
        f"/api/runs/{run_id}/director/events",
        json={
            "event_type": "shutdown",
            "payload": {"message": "Town square closed", "duration_ticks": 4},
            "location_id": square.id,
            "importance": 0.8,
        },
    )
    timeline_response = await client.get(f"/api/runs/{run_id}/timeline")

    run = await db_session.get(SimulationRun, run_id)
    world_effects = (run.metadata_json or {}).get("world_effects", {})
    location_shutdowns = world_effects.get("location_shutdowns", [])

    assert inject_response.status_code == 200
    assert inject_response.json()["status"] == "queued"
    assert len(location_shutdowns) == 1
    assert location_shutdowns[0]["location_id"] == square.id
    assert location_shutdowns[0]["message"] == "Town square closed"
    assert location_shutdowns[0]["end_tick"] == location_shutdowns[0]["start_tick"] + 4

    timeline = timeline_response.json()
    assert any(event["event_type"] == "director_shutdown" for event in timeline["events"])


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
            Agent(
                id="agent-delete-a",
                run_id=run_id,
                name="Alice",
                occupation="resident",
                current_location_id="loc-delete",
                personality={},
                profile={},
                status={},
                current_plan={},
            ),
            Agent(
                id="agent-delete-b",
                run_id=run_id,
                name="Bob",
                occupation="resident",
                personality={},
                profile={},
                status={},
                current_plan={},
            ),
            Location(id="loc-delete", run_id=run_id, name="Cafe", location_type="cafe", capacity=4),
            Event(
                id="event-delete",
                run_id=run_id,
                tick_no=1,
                event_type="talk",
                actor_agent_id="agent-delete-a",
                target_agent_id="agent-delete-b",
                location_id="loc-delete",
                payload={},
            ),
            Memory(
                id="memory-delete",
                run_id=run_id,
                agent_id="agent-delete-a",
                tick_no=1,
                memory_type="episodic_long",
                memory_category="long_term",
                content="Talked with Bob",
                summary="Talked with Bob",
                importance=0.9,
                related_agent_id="agent-delete-b",
                location_id="loc-delete",
                metadata_json={},
            ),
            Relationship(
                id="relationship-delete",
                run_id=run_id,
                agent_id="agent-delete-a",
                other_agent_id="agent-delete-b",
                familiarity=0.3,
                trust=0.2,
                affinity=0.4,
                relation_type="friend",
            ),
            DirectorMemory(
                id="director-memory-delete",
                run_id=run_id,
                tick_no=1,
                scene_goal="gather",
                target_agent_ids='["agent-delete-b"]',
                message_hint="Meet now",
                was_executed=False,
            ),
            GovernanceRecord(
                id="governance-record-delete",
                run_id=run_id,
                agent_id="agent-delete-a",
                tick_no=1,
                source_event_id="event-delete",
                location_id="loc-delete",
                action_type="work",
                decision="warn",
            ),
            GovernanceCase(
                id="governance-case-delete",
                run_id=run_id,
                agent_id="agent-delete-a",
                primary_reason="Repeated policy violation",
            ),
            GovernanceRestriction(
                id="governance-restriction-delete",
                run_id=run_id,
                agent_id="agent-delete-a",
                case_id="governance-case-delete",
                restriction_type="work_ban",
            ),
            AgentEconomicState(
                id="economic-state-delete",
                run_id=run_id,
                agent_id="agent-delete-a",
            ),
            EconomicEffectLog(
                id="economic-log-delete",
                run_id=run_id,
                agent_id="agent-delete-a",
                case_id="governance-case-delete",
                tick_no=1,
                effect_type="governance_work_loss",
            ),
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
    assert await db_session.get(GovernanceRecord, "governance-record-delete") is None
    assert await db_session.get(GovernanceCase, "governance-case-delete") is None
    assert await db_session.get(GovernanceRestriction, "governance-restriction-delete") is None
    assert await db_session.get(AgentEconomicState, "economic-state-delete") is None
    assert await db_session.get(EconomicEffectLog, "economic-log-delete") is None


@pytest.mark.asyncio
async def test_delete_run_returns_404_for_missing_run_and_still_cleans_runtime_resources(
    client, monkeypatch: pytest.MonkeyPatch
):
    fake_registry = _FakeCognitionRegistry()
    monkeypatch.setattr(runs_route, "get_cognition_registry", lambda: fake_registry)

    response = await client.delete("/api/runs/00000000-0000-0000-0000-000000000208")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Run not found",
        "code": "RUN_NOT_FOUND",
        "context": {"run_id": "00000000-0000-0000-0000-000000000208"},
    }
    assert fake_registry.cleaned_runs == ["00000000-0000-0000-0000-000000000208"]
