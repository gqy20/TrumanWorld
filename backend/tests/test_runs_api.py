import pytest


@pytest.mark.asyncio
async def test_health_check(client):
    response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_create_run_returns_draft_run(client):
    response = await client.post("/api/runs", json={"name": "test-run"})

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "test-run"
    assert body["status"] == "draft"
    assert body["id"]


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
async def test_get_timeline_for_empty_run(client):
    create_response = await client.post("/api/runs", json={"name": "timeline-run"})
    run_id = create_response.json()["id"]

    timeline_response = await client.get(f"/api/runs/{run_id}/timeline")

    assert timeline_response.status_code == 200
    assert timeline_response.json() == {"run_id": run_id, "events": []}


@pytest.mark.asyncio
async def test_run_not_found_returns_404(client):
    response = await client.get("/api/runs/00000000-0000-0000-0000-000000000001")

    assert response.status_code == 404
    assert response.json()["detail"] == "Run not found"
