import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.api.routes.system as system_route
import app.api.routes.runs as runs_route
import app.sim.day_boundary_coordinator as day_boundary_coordinator_module
from app.store.models import (
    Agent,
    DirectorMemory,
    Event,
    Location,
    Memory,
    Relationship,
    SimulationRun,
)
from app.sim.scheduler import get_scheduler

RUN_COMMON_FIELDS = {
    "id",
    "name",
    "status",
    "scenario_type",
    "current_tick",
    "tick_minutes",
    "was_running_before_restart",
    "started_at",
    "elapsed_seconds",
}


def assert_run_common_fields(payload: dict) -> None:
    assert RUN_COMMON_FIELDS <= payload.keys()


@pytest.mark.asyncio
async def test_health_check(client):
    response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_metrics_endpoint_exposes_runtime_metrics(client):
    response = await client.get("/api/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    body = response.text
    assert "trumanworld_tick_total" in body
    assert "trumanworld_tick_duration_seconds" in body
    assert "trumanworld_active_runs" in body
    assert "trumanworld_claude_reactor_pool_enabled" in body
    assert "trumanworld_claude_reactor_pool_size" in body
    assert "trumanworld_claude_reactor_pool_active" in body
    assert "process_resident_memory_bytes" in body


@pytest.mark.asyncio
async def test_system_overview_endpoint_returns_project_components(
    client, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        system_route,
        "get_system_overview_payload",
        lambda: {
            "collected_at": 1234567890,
            "components": {
                "backend": {
                    "status": "available",
                    "rss_bytes": 100,
                    "unique_bytes": 90,
                    "vms_bytes": 200,
                    "cpu_seconds": 3.5,
                    "cpu_percent": 25.0,
                    "process_count": 1,
                },
                "frontend": {
                    "status": "available",
                    "rss_bytes": 300,
                    "unique_bytes": 280,
                    "vms_bytes": 400,
                    "cpu_seconds": 2.0,
                    "cpu_percent": 50.0,
                    "process_count": 2,
                },
                "postgres": {
                    "status": "unavailable",
                    "rss_bytes": 0,
                    "unique_bytes": None,
                    "vms_bytes": 0,
                    "cpu_seconds": 0.0,
                    "cpu_percent": 0.0,
                    "process_count": 0,
                },
                "total": {
                    "status": "available",
                    "rss_bytes": 400,
                    "unique_bytes": 370,
                    "vms_bytes": 600,
                    "cpu_seconds": 5.5,
                    "cpu_percent": 75.0,
                    "process_count": 3,
                },
            },
        },
    )

    response = await client.get("/api/system/overview")

    assert response.status_code == 200
    body = response.json()
    assert body["collected_at"] == 1234567890
    assert body["components"]["backend"]["cpu_percent"] == 25.0
    assert body["components"]["backend"]["rss_bytes"] == 100
    assert body["components"]["backend"]["unique_bytes"] == 90
    assert body["components"]["frontend"]["process_count"] == 2
    assert body["components"]["postgres"]["status"] == "unavailable"
    assert body["components"]["total"]["rss_bytes"] == 400


@pytest.mark.asyncio
async def test_cors_preflight_allows_frontend_origin(client):
    response = await client.options(
        "/api/runs",
        headers={
            "Origin": "http://127.0.0.1:33100",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:33100"


@pytest.mark.asyncio
async def test_create_run_returns_running_status(client):
    """Test that create run returns running status with auto-scheduler."""
    response = await client.post("/api/runs", json={"name": "test-run"})

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "test-run"
    assert body["status"] == "running"  # Auto-started with scheduler
    assert body["scenario_type"] == "truman_world"
    assert body["id"]
    assert get_scheduler().is_running(body["id"])

    agents_response = await client.get(f"/api/runs/{body['id']}/agents")
    assert agents_response.status_code == 200
    assert (
        len(agents_response.json()["agents"]) == 6
    )  # truman, spouse, friend, neighbor, alice, bob


@pytest.mark.asyncio
async def test_create_open_world_run_uses_open_world_scenario(client):
    response = await client.post(
        "/api/runs",
        json={"name": "open-world-run", "scenario_type": "open_world"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["scenario_type"] == "open_world"
    assert get_scheduler().is_running(body["id"])

    agents_response = await client.get(f"/api/runs/{body['id']}/agents")
    assert agents_response.status_code == 200
    assert len(agents_response.json()["agents"]) == 1
    assert agents_response.json()["agents"][0]["name"] == "Rover"


@pytest.mark.asyncio
async def test_list_runs_returns_created_runs(client):
    await client.post("/api/runs", json={"name": "run-a"})
    await client.post("/api/runs", json={"name": "run-b", "seed_demo": False})

    response = await client.get("/api/runs")

    assert response.status_code == 200
    names = {item["name"] for item in response.json()}
    assert {"run-a", "run-b"} <= names


@pytest.mark.asyncio
async def test_list_runs_includes_aggregated_counts(client, db_session: AsyncSession):
    run_id = "00000000-0000-0000-0000-000000000201"
    db_session.add_all(
        [
            SimulationRun(id=run_id, name="counted-run", status="running"),
            Agent(
                id="agent-count-1",
                run_id=run_id,
                name="Alice",
                occupation="resident",
                personality={},
                profile={},
                status={},
                current_plan={},
            ),
            Agent(
                id="agent-count-2",
                run_id=run_id,
                name="Bob",
                occupation="resident",
                personality={},
                profile={},
                status={},
                current_plan={},
            ),
            Location(
                id="loc-count-1",
                run_id=run_id,
                name="Cafe",
                location_type="cafe",
                capacity=4,
            ),
            Event(
                id="event-count-1",
                run_id=run_id,
                tick_no=1,
                event_type="talk",
                payload={},
            ),
        ]
    )
    await db_session.commit()

    response = await client.get("/api/runs")

    assert response.status_code == 200
    run = next(item for item in response.json() if item["id"] == run_id)
    assert run["agent_count"] == 2
    assert run["location_count"] == 1
    assert run["event_count"] == 1


@pytest.mark.asyncio
async def test_run_status_transitions(client):
    create_response = await client.post("/api/runs", json={"name": "stateful-run"})
    run_id = create_response.json()["id"]

    start_response = await client.post(f"/api/runs/{run_id}/start")
    assert start_response.status_code == 200
    assert start_response.json()["status"] == "running"
    assert get_scheduler().is_running(run_id)

    pause_response = await client.post(f"/api/runs/{run_id}/pause")
    assert pause_response.status_code == 200
    assert pause_response.json()["status"] == "paused"
    assert not get_scheduler().is_running(run_id)

    resume_response = await client.post(f"/api/runs/{run_id}/resume")
    assert resume_response.status_code == 200
    assert resume_response.json()["status"] == "running"
    assert get_scheduler().is_running(run_id)


@pytest.mark.asyncio
async def test_restore_all_runs_restarts_scheduler_and_clears_flag(
    client, db_session: AsyncSession
):
    create_response = await client.post("/api/runs", json={"name": "restore-run"})
    run_id = create_response.json()["id"]

    await client.post(f"/api/runs/{run_id}/pause")

    # Simulate an interrupted run that should be restored.
    run_response = await client.get(f"/api/runs/{run_id}")
    assert run_response.status_code == 200

    run = await db_session.get(SimulationRun, run_id)
    assert run is not None
    run.status = "paused"
    run.was_running_before_restart = True
    await db_session.commit()

    restore_response = await client.post("/api/runs/restore-all")

    assert restore_response.status_code == 200
    restored = restore_response.json()
    assert len(restored) == 1
    assert restored[0]["id"] == run_id
    assert restored[0]["status"] == "running"
    assert restored[0]["was_running_before_restart"] is False
    assert get_scheduler().is_running(run_id)


@pytest.mark.asyncio
async def test_run_endpoints_return_consistent_common_fields(client, db_session: AsyncSession):
    create_response = await client.post("/api/runs", json={"name": "shape-run"})
    run_id = create_response.json()["id"]

    list_response = await client.get("/api/runs")
    detail_response = await client.get(f"/api/runs/{run_id}")
    pause_response = await client.post(f"/api/runs/{run_id}/pause")
    resume_response = await client.post(f"/api/runs/{run_id}/resume")

    run = await db_session.get(SimulationRun, run_id)
    assert run is not None
    run.status = "paused"
    run.was_running_before_restart = True
    await db_session.commit()

    restore_response = await client.post("/api/runs/restore-all")

    assert create_response.status_code == 200
    assert list_response.status_code == 200
    assert detail_response.status_code == 200
    assert pause_response.status_code == 200
    assert resume_response.status_code == 200
    assert restore_response.status_code == 200

    list_item = next(item for item in list_response.json() if item["id"] == run_id)
    restore_item = next(item for item in restore_response.json() if item["id"] == run_id)

    for payload in (
        create_response.json(),
        list_item,
        detail_response.json(),
        pause_response.json(),
        resume_response.json(),
        restore_item,
    ):
        assert_run_common_fields(payload)

    assert {"agent_count", "location_count", "event_count"} <= list_item.keys()


@pytest.mark.asyncio
async def test_advance_run_tick_updates_tick_counter(client):
    create_response = await client.post("/api/runs", json={"name": "tick-run", "seed_demo": False})
    run_id = create_response.json()["id"]

    tick_response = await client.post(f"/api/runs/{run_id}/tick")
    run_response = await client.get(f"/api/runs/{run_id}")

    assert tick_response.status_code == 200
    assert tick_response.json()["tick_no"] == 1
    assert tick_response.json()["accepted_count"] == 0
    assert tick_response.json()["rejected_count"] == 0

    assert run_response.status_code == 200
    assert run_response.json()["current_tick"] == 1


@pytest.mark.asyncio
async def test_advance_run_tick_for_empty_run_skips_sleep_hours(client, db_session: AsyncSession):
    run_id = "00000000-0000-0000-0000-000000000301"
    db_session.add(
        SimulationRun(
            id=run_id,
            name="clock-api-empty-run",
            status="running",
            current_tick=203,
            tick_minutes=5,
            metadata_json={"world_start_time": "2026-03-02T06:00:00+00:00"},
        )
    )
    await db_session.commit()

    tick_response = await client.post(f"/api/runs/{run_id}/tick")
    world_response = await client.get(f"/api/runs/{run_id}/world")

    assert tick_response.status_code == 200
    assert tick_response.json()["tick_no"] == 288
    assert tick_response.json()["accepted_count"] == 0
    assert tick_response.json()["rejected_count"] == 0

    assert world_response.status_code == 200
    assert world_response.json()["run"]["current_tick"] == 288
    assert world_response.json()["world_clock"]["iso"] == "2026-03-03T06:00:00+00:00"


@pytest.mark.asyncio
async def test_advance_run_tick_triggers_morning_planner(
    client, db_session: AsyncSession, monkeypatch
):
    run_id = "00000000-0000-0000-0000-000000000303"
    db_session.add(
        SimulationRun(
            id=run_id,
            name="clock-api-morning-planner",
            status="running",
            current_tick=0,
            tick_minutes=5,
            metadata_json={"world_start_time": "2026-03-02T06:00:00+00:00"},
        )
    )
    await db_session.commit()

    calls: list[tuple[str, int]] = []

    async def fake_run_morning_planning(*, run_id: str, tick_no: int, world, engine, agent_runtime):
        calls.append((run_id, tick_no))

    monkeypatch.setattr(
        day_boundary_coordinator_module, "run_morning_planning", fake_run_morning_planning
    )

    tick_response = await client.post(f"/api/runs/{run_id}/tick")

    assert tick_response.status_code == 200
    assert tick_response.json()["tick_no"] == 1
    assert calls == [(run_id, 0)]


@pytest.mark.asyncio
async def test_advance_run_tick_triggers_evening_reflector(
    client, db_session: AsyncSession, monkeypatch
):
    run_id = "00000000-0000-0000-0000-000000000304"
    db_session.add(
        SimulationRun(
            id=run_id,
            name="clock-api-evening-reflector",
            status="running",
            current_tick=191,
            tick_minutes=5,
            metadata_json={"world_start_time": "2026-03-02T06:00:00+00:00"},
        )
    )
    await db_session.commit()

    calls: list[tuple[str, int]] = []

    async def fake_run_evening_reflection(
        *, run_id: str, tick_no: int, world, engine, agent_runtime
    ):
        calls.append((run_id, tick_no))

    monkeypatch.setattr(
        day_boundary_coordinator_module,
        "run_evening_reflection",
        fake_run_evening_reflection,
    )

    tick_response = await client.post(f"/api/runs/{run_id}/tick")

    assert tick_response.status_code == 200
    assert tick_response.json()["tick_no"] == 192
    assert calls == [(run_id, 192)]


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


# ============================================================
# Events Incremental Query Tests
# ============================================================


@pytest.mark.asyncio
async def test_events_incremental_query_with_since_tick(client, db_session):
    """测试 since_tick 参数只返回指定 tick 之后的事件。"""
    create_response = await client.post("/api/runs", json={"name": "incremental-test"})
    run_id = create_response.json()["id"]

    # 手动插入不同 tick 的事件
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

    # 查询 tick > 2 的事件
    response = await client.get(f"/api/runs/{run_id}/events", params={"since_tick": 2})
    assert response.status_code == 200
    data = response.json()
    tick_nos = [e["tick_no"] for e in data["events"]]

    # 只应该返回 tick 5 和 7
    assert all(t > 2 for t in tick_nos)
    assert 1 not in tick_nos
    assert 2 not in tick_nos


@pytest.mark.asyncio
async def test_events_incremental_query_returns_latest_tick(client, db_session):
    """测试响应中包含 latest_tick 字段，供前端下次查询使用。"""
    create_response = await client.post("/api/runs", json={"name": "latest-tick-test"})
    run_id = create_response.json()["id"]

    db_session.add_all(
        [
            Event(
                id="lt-event-1",
                run_id=run_id,
                tick_no=1,
                event_type="talk",
                payload={},
            ),
            Event(
                id="lt-event-2",
                run_id=run_id,
                tick_no=5,
                event_type="move",
                payload={},
            ),
        ]
    )
    await db_session.commit()

    response = await client.get(f"/api/runs/{run_id}/events")
    assert response.status_code == 200
    data = response.json()

    # latest_tick 应该是最大 tick_no
    assert "latest_tick" in data
    assert data["latest_tick"] == 5


@pytest.mark.asyncio
async def test_events_incremental_query_empty_since_tick(client, db_session):
    """测试 since_tick 超过当前最大 tick 时返回空列表。"""
    create_response = await client.post("/api/runs", json={"name": "empty-incremental"})
    run_id = create_response.json()["id"]

    db_session.add_all(
        [
            Event(
                id="empty-event-1",
                run_id=run_id,
                tick_no=1,
                event_type="talk",
                payload={},
            ),
            Event(
                id="empty-event-2",
                run_id=run_id,
                tick_no=2,
                event_type="move",
                payload={},
            ),
        ]
    )
    await db_session.commit()

    # since_tick=100 超过了最大 tick 2
    response = await client.get(f"/api/runs/{run_id}/events", params={"since_tick": 100})
    assert response.status_code == 200
    data = response.json()

    assert len(data["events"]) == 0
    assert data["total"] == 0


class _FakePool:
    def __init__(self) -> None:
        self.cleaned_runs: list[str] = []

    async def cleanup_run(self, run_id: str) -> int:
        self.cleaned_runs.append(run_id)
        return 1


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
    assert (
        len(body["locations"]) == 7
    )  # plaza, apartment, office, cafe, hospital, bachelor-apt, mall
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
    assert body["truman_agent_id"]
    assert body["suspicion_level"] in {"low", "guarded", "alerted", "high"}
    assert body["continuity_risk"] in {"stable", "watch", "elevated", "critical"}
    assert isinstance(body["notes"], list)
    assert isinstance(body["focus_agent_ids"], list)


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
                id="timeline-order-talk",
                run_id=run_id,
                tick_no=2,
                event_type="talk",
                payload={},
            ),
            Event(
                id="timeline-order-move",
                run_id=run_id,
                tick_no=5,
                event_type="move",
                payload={},
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
    monkeypatch.setattr(
        runs_route,
        "get_cognition_registry",
        lambda: fake_registry,
    )

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
            Location(
                id="loc-delete",
                run_id=run_id,
                name="Cafe",
                location_type="cafe",
                capacity=4,
            ),
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
                target_cast_ids='["agent-delete-b"]',
                message_hint="Meet now",
                was_executed=False,
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


@pytest.mark.asyncio
async def test_delete_run_returns_404_for_missing_run_and_still_cleans_runtime_resources(
    client, monkeypatch: pytest.MonkeyPatch
):
    fake_registry = _FakeCognitionRegistry()
    monkeypatch.setattr(
        runs_route,
        "get_cognition_registry",
        lambda: fake_registry,
    )

    response = await client.delete("/api/runs/00000000-0000-0000-0000-000000000208")

    assert response.status_code == 404
    assert response.json()["detail"] == "Run not found"
    assert fake_registry.cleaned_runs == ["00000000-0000-0000-0000-000000000208"]
