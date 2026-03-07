import pytest


@pytest.mark.asyncio
async def test_health_check(client):
    response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


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
    assert body["id"]

    agents_response = await client.get(f"/api/runs/{body['id']}/agents")
    assert agents_response.status_code == 200
    assert len(agents_response.json()["agents"]) == 4


@pytest.mark.asyncio
async def test_list_runs_returns_created_runs(client):
    await client.post("/api/runs", json={"name": "run-a"})
    await client.post("/api/runs", json={"name": "run-b", "seed_demo": False})

    response = await client.get("/api/runs")

    assert response.status_code == 200
    names = {item["name"] for item in response.json()}
    assert {"run-a", "run-b"} <= names


@pytest.mark.asyncio
async def test_run_status_transitions(client):
    create_response = await client.post("/api/runs", json={"name": "stateful-run"})
    run_id = create_response.json()["id"]

    start_response = await client.post(f"/api/runs/{run_id}/start")
    pause_response = await client.post(f"/api/runs/{run_id}/pause")
    resume_response = await client.post(f"/api/runs/{run_id}/resume")

    assert start_response.status_code == 200
    assert start_response.json()["status"] == "running"

    assert pause_response.status_code == 200
    assert pause_response.json()["status"] == "paused"

    assert resume_response.status_code == 200
    assert resume_response.json()["status"] == "running"


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
async def test_get_timeline_for_empty_run(client):
    create_response = await client.post(
        "/api/runs", json={"name": "timeline-run", "seed_demo": False}
    )
    run_id = create_response.json()["id"]

    timeline_response = await client.get(f"/api/runs/{run_id}/timeline")

    assert timeline_response.status_code == 200
    assert timeline_response.json() == {"run_id": run_id, "events": []}


@pytest.mark.asyncio
async def test_get_world_snapshot_returns_locations_agents_and_public_events(client):
    create_response = await client.post("/api/runs", json={"name": "world-run"})
    run_id = create_response.json()["id"]

    await client.post(f"/api/runs/{run_id}/tick")
    world_response = await client.get(f"/api/runs/{run_id}/world")

    assert world_response.status_code == 200
    body = world_response.json()
    assert body["run"]["id"] == run_id
    assert len(body["locations"]) == 4
    assert any(len(location["occupants"]) >= 1 for location in body["locations"])
    assert len(body["recent_events"]) >= 1


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
