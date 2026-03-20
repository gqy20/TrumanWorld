import pytest
from sqlalchemy.ext.asyncio import AsyncSession

import app.api.routes.system as system_route
import app.sim.day_boundary_coordinator as day_boundary_coordinator_module
from app.infra.settings import get_settings
from app.sim.scheduler import get_scheduler
from app.store.models import Agent, Event, Location, SimulationRun

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
async def test_system_access_reports_demo_mode_status(client, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TRUMANWORLD_DEMO_ADMIN_PASSWORD", "secret-demo-password")
    get_settings.cache_clear()

    try:
        response = await client.get("/api/system/access")

        assert response.status_code == 200
        assert response.json() == {
            "write_protected": True,
            "admin_authorized": False,
        }

        unlocked_response = await client.get(
            "/api/system/access",
            headers={"x-demo-admin-password": "secret-demo-password"},
        )
        assert unlocked_response.status_code == 200
        assert unlocked_response.json() == {
            "write_protected": True,
            "admin_authorized": True,
        }
    finally:
        get_settings.cache_clear()


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
async def test_create_run_requires_admin_header_when_demo_password_configured(
    client, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("TRUMANWORLD_DEMO_ADMIN_PASSWORD", "secret-demo-password")
    get_settings.cache_clear()

    try:
        unauthorized = await client.post("/api/runs", json={"name": "blocked-run"})
        assert unauthorized.status_code == 401
        assert unauthorized.json()["detail"] == "Admin access required for write operations"

        authorized = await client.post(
            "/api/runs",
            json={"name": "allowed-run"},
            headers={"x-demo-admin-password": "secret-demo-password"},
        )
        assert authorized.status_code == 200
        assert authorized.json()["name"] == "allowed-run"
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_create_run_returns_running_status(client):
    response = await client.post("/api/runs", json={"name": "test-run"})

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "test-run"
    assert body["status"] == "running"
    assert body["scenario_type"] == "truman_world"
    assert body["id"]
    assert get_scheduler().is_running(body["id"])

    agents_response = await client.get(f"/api/runs/{body['id']}/agents")
    assert agents_response.status_code == 200
    assert len(agents_response.json()["agents"]) == 6


@pytest.mark.asyncio
async def test_create_run_accepts_missing_scenario_type_and_uses_default(client):
    response = await client.post(
        "/api/runs",
        json={"name": "default-scenario-run", "seed_demo": False},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "default-scenario-run"
    assert body["scenario_type"] == "truman_world"


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
async def test_create_run_rejects_unknown_scenario_type(client):
    response = await client.post(
        "/api/runs",
        json={"name": "invalid-scenario-run", "scenario_type": "missing_world"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Unknown scenario_type: missing_world"


@pytest.mark.asyncio
async def test_list_scenarios_returns_registered_bundles(client):
    response = await client.get("/api/scenarios")

    assert response.status_code == 200
    body = response.json()
    assert {"id": "open_world", "name": "Open World", "version": 1} in body
    assert {"id": "truman_world", "name": "Truman World", "version": 1} in body


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
            Agent(id="agent-count-1", run_id=run_id, name="Alice", occupation="resident", personality={}, profile={}, status={}, current_plan={}),
            Agent(id="agent-count-2", run_id=run_id, name="Bob", occupation="resident", personality={}, profile={}, status={}, current_plan={}),
            Location(id="loc-count-1", run_id=run_id, name="Cafe", location_type="cafe", capacity=4),
            Event(id="event-count-1", run_id=run_id, tick_no=1, event_type="talk", payload={}),
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
