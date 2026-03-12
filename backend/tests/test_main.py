from __future__ import annotations

from types import SimpleNamespace

import pytest

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
