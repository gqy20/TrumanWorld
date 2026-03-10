from __future__ import annotations

import pytest

import app.sim.bootstrap as bootstrap_module
from app.store.models import Agent, SimulationRun


class FakePool:
    def __init__(self) -> None:
        self.warmup_calls: list[list[str]] = []

    async def warmup(self, agent_ids: list[str]) -> int:
        self.warmup_calls.append(agent_ids)
        return len(agent_ids)


class FakeService:
    def __init__(self) -> None:
        self.run_tick_calls: list[tuple[str, object]] = []

    async def run_tick_isolated(self, run_id: str, engine) -> None:
        self.run_tick_calls.append((run_id, engine))


@pytest.mark.asyncio
async def test_bootstrapper_warms_pool_and_builds_tick_callback(db_session, tmp_path):
    run = SimulationRun(
        id="run-bootstrap-1",
        name="demo",
        status="running",
        scenario_type="truman_world",
    )
    db_session.add_all(
        [
            run,
            Agent(
                id="run-bootstrap-1-alice",
                run_id="run-bootstrap-1",
                name="Alice",
                occupation="barista",
                profile={"agent_config_id": "spouse"},
                personality={},
                status={},
                current_plan={},
            ),
            Agent(
                id="run-bootstrap-1-bob",
                run_id="run-bootstrap-1",
                name="Bob",
                occupation="resident",
                profile={},
                personality={},
                status={},
                current_plan={},
            ),
        ]
    )
    await db_session.commit()

    pool = FakePool()
    created_registry_paths: list[object] = []
    created_runtimes: list[tuple[object, object]] = []
    created_services: list[FakeService] = []
    fake_engine = object()
    scenario = object()

    class FakeRegistry:
        def __init__(self, path) -> None:
            created_registry_paths.append(path)

    class FakeRuntime:
        def __init__(self, registry, connection_pool) -> None:
            created_runtimes.append((registry, connection_pool))

    def fake_create_scenario(scenario_type: str):
        assert scenario_type == "truman_world"
        return scenario

    def fake_create_for_scheduler(agent_runtime, scenario):
        service = FakeService()
        created_services.append(service)
        return service

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        bootstrap_module,
        "get_settings",
        lambda: type(
            "S",
            (),
            {"project_root": tmp_path, "scheduler_interval_seconds": 7.5},
        )(),
    )
    monkeypatch.setattr(bootstrap_module, "get_connection_pool", lambda: _return_async(pool))
    monkeypatch.setattr(bootstrap_module, "AgentRegistry", FakeRegistry)
    monkeypatch.setattr(bootstrap_module, "AgentRuntime", FakeRuntime)
    monkeypatch.setattr(bootstrap_module, "create_scenario", fake_create_scenario)
    monkeypatch.setattr(
        bootstrap_module.SimulationService,
        "create_for_scheduler",
        fake_create_for_scheduler,
    )
    monkeypatch.setattr(bootstrap_module, "async_engine", fake_engine)
    try:
        plan = await bootstrap_module.RunExecutionBootstrapper().prepare(db_session, run)
        await plan.tick_callback(run.id)
    finally:
        monkeypatch.undo()

    assert plan.interval_seconds == 7.5
    assert created_registry_paths == [tmp_path / "agents"]
    assert len(created_runtimes) == 1
    assert created_runtimes[0][1] is pool
    assert pool.warmup_calls == [
        [
            "run-bootstrap-1:run-bootstrap-1-bob",
            "run-bootstrap-1:spouse",
        ]
    ]
    assert len(created_services) == 1
    assert created_services[0].run_tick_calls == [("run-bootstrap-1", fake_engine)]


@pytest.mark.asyncio
async def test_bootstrapper_skips_warmup_when_run_has_no_agents(db_session, tmp_path):
    run = SimulationRun(id="run-bootstrap-2", name="demo", status="running")
    db_session.add(run)
    await db_session.commit()

    pool = FakePool()

    class FakeRegistry:
        def __init__(self, path) -> None:
            self.path = path

    class FakeRuntime:
        def __init__(self, registry, connection_pool) -> None:
            self.registry = registry
            self.connection_pool = connection_pool

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        bootstrap_module,
        "get_settings",
        lambda: type(
            "S",
            (),
            {"project_root": tmp_path, "scheduler_interval_seconds": 5.0},
        )(),
    )
    monkeypatch.setattr(bootstrap_module, "get_connection_pool", lambda: _return_async(pool))
    monkeypatch.setattr(bootstrap_module, "AgentRegistry", FakeRegistry)
    monkeypatch.setattr(bootstrap_module, "AgentRuntime", FakeRuntime)
    monkeypatch.setattr(bootstrap_module, "create_scenario", lambda _: object())
    monkeypatch.setattr(
        bootstrap_module.SimulationService,
        "create_for_scheduler",
        lambda agent_runtime, scenario: FakeService(),
    )
    try:
        plan = await bootstrap_module.RunExecutionBootstrapper().prepare(db_session, run)
    finally:
        monkeypatch.undo()

    assert plan.interval_seconds == 5.0
    assert pool.warmup_calls == []


async def _return_async(value):
    return value
