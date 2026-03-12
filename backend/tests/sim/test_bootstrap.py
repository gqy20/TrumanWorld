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


class FakeCognitionRegistry:
    def __init__(self) -> None:
        self.warmup_calls: list[tuple[object, str]] = []
        self.cleanup_idle_calls = 0

    async def warmup_for_run(self, session, run_id: str) -> None:
        self.warmup_calls.append((session, run_id))

    async def cleanup_idle(self) -> None:
        self.cleanup_idle_calls += 1


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

    cognition_registry = FakeCognitionRegistry()
    created_registry_paths: list[object] = []
    created_runtimes: list[tuple[object, object, object]] = []
    created_services: list[FakeService] = []
    fake_engine = object()
    scenario = object()

    class FakeRegistry:
        def __init__(self, path) -> None:
            created_registry_paths.append(path)

    class FakeRuntime:
        def __init__(self, registry, cognition_registry) -> None:
            created_runtimes.append((registry, cognition_registry, self))

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
    monkeypatch.setattr(
        bootstrap_module,
        "get_cognition_registry",
        lambda: cognition_registry,
    )
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
    assert created_runtimes[0][1] is cognition_registry
    assert cognition_registry.warmup_calls == [(db_session, "run-bootstrap-1")]
    assert cognition_registry.cleanup_idle_calls == 1
    assert len(created_services) == 1
    assert created_services[0].run_tick_calls == [("run-bootstrap-1", fake_engine)]


@pytest.mark.asyncio
async def test_bootstrapper_skips_warmup_when_run_has_no_agents(db_session, tmp_path):
    run = SimulationRun(id="run-bootstrap-2", name="demo", status="running")
    db_session.add(run)
    await db_session.commit()

    cognition_registry = FakeCognitionRegistry()

    class FakeRegistry:
        def __init__(self, path) -> None:
            self.path = path

    class FakeRuntime:
        def __init__(self, registry, cognition_registry) -> None:
            self.registry = registry
            self.cognition_registry = cognition_registry

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
    monkeypatch.setattr(
        bootstrap_module,
        "get_cognition_registry",
        lambda: cognition_registry,
    )
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
    assert cognition_registry.warmup_calls == [(db_session, "run-bootstrap-2")]


@pytest.mark.asyncio
async def test_bootstrapper_skips_pool_setup_when_reactor_pool_disabled(db_session, tmp_path):
    run = SimulationRun(id="run-bootstrap-3", name="demo", status="running")
    db_session.add(run)
    await db_session.commit()

    class FakeRegistry:
        def __init__(self, path) -> None:
            self.path = path

    class FakeRuntime:
        def __init__(self, registry, cognition_registry=None) -> None:
            self.registry = registry
            self.cognition_registry = cognition_registry

    monkeypatch = pytest.MonkeyPatch()
    cognition_registry = FakeCognitionRegistry()

    async def fake_warmup_for_run(session, run_id: str) -> None:
        raise AssertionError("warmup_for_run should not be called when pool is disabled")

    cognition_registry.warmup_for_run = fake_warmup_for_run  # type: ignore[method-assign]

    monkeypatch.setattr(
        bootstrap_module,
        "get_settings",
        lambda: type(
            "S",
            (),
            {
                "project_root": tmp_path,
                "scheduler_interval_seconds": 5.0,
                "claude_sdk_reactor_pool_enabled": False,
            },
        )(),
    )
    monkeypatch.setattr(
        bootstrap_module,
        "get_cognition_registry",
        lambda: cognition_registry,
    )
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
