from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import status

import app.main as main_module


@pytest.mark.asyncio
async def test_lifespan_shutdown_stops_scheduler_and_closes_connection_pool(monkeypatch):
    calls: list[str] = []

    class FakeScheduler:
        async def stop_all(self) -> None:
            calls.append("scheduler.stop_all")

    class FakeCognitionRegistry:
        async def cleanup(self) -> None:
            calls.append("connection_pool.close")

    monkeypatch.setattr(main_module, "get_db_session_context", lambda: _empty_session_context())

    import app.sim.scheduler as scheduler_module
    import app.cognition.registry as cognition_registry_module

    monkeypatch.setattr(scheduler_module, "get_scheduler", lambda: FakeScheduler())
    monkeypatch.setattr(
        cognition_registry_module,
        "get_cognition_registry",
        lambda: FakeCognitionRegistry(),
    )

    app = SimpleNamespace()
    async with main_module.lifespan(app):
        pass

    assert calls == ["scheduler.stop_all", "connection_pool.close"]


async def _empty_session_context():
    if False:
        yield None


@pytest.mark.asyncio
async def test_http_exception_handler_returns_normalized_error_payload(client):
    response = await client.get("/api/runs/00000000-0000-0000-0000-000000000001")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {
        "detail": "Run not found",
        "code": "RUN_NOT_FOUND",
        "context": {"run_id": "00000000-0000-0000-0000-000000000001"},
    }


@pytest.mark.asyncio
async def test_request_logging_middleware_reports_database_activity(client, monkeypatch):
    observations: list[dict] = []
    http_observations: list[dict] = []
    monkeypatch.setattr(
        main_module,
        "observe_database_operation",
        lambda **fields: observations.append(fields),
    )
    monkeypatch.setattr(
        main_module,
        "observe_http_request",
        lambda **fields: http_observations.append(fields),
    )

    response = await client.get("/api/health", headers={"x-request-id": "req-test-123"})

    assert response.status_code == status.HTTP_200_OK
    assert response.headers["x-request-id"] == "req-test-123"
    assert observations == [
        {
            "operation": "http.health_check",
            "query_count": 0,
            "duration_seconds": 0.0,
        }
    ]
    assert http_observations == [
        {
            "method": "GET",
            "route": "/api/health",
            "status_code": 200,
            "duration_seconds": pytest.approx(0, abs=1),
        }
    ]
