import pytest

import app.sim.run_lifecycle as run_lifecycle_module
from app.store.models import Agent, SimulationRun
from app.store.repositories import RunRepository


class FakeScheduler:
    def __init__(self, *, running: bool) -> None:
        self.running = running
        self.started: list[tuple[str, float, object]] = []
        self.stopped: list[str] = []

    def is_running(self, run_id: str) -> bool:
        return self.running

    async def start_run(self, run_id: str, interval_seconds: float, callback) -> None:
        self.started.append((run_id, interval_seconds, callback))

    async def stop_run(self, run_id: str) -> None:
        self.stopped.append(run_id)


class FakePool:
    def __init__(self) -> None:
        self.cleanup_calls: list[str] = []

    async def cleanup_run(self, run_id: str) -> int:
        self.cleanup_calls.append(run_id)
        return 1


class FakeCognitionRegistry:
    def __init__(self, cleanup_result: int = 1) -> None:
        self.cleanup_calls: list[str] = []
        self.cleanup_result = cleanup_result

    async def cleanup_run(self, run_id: str) -> int:
        self.cleanup_calls.append(run_id)
        return self.cleanup_result


class FakePlan:
    def __init__(self, interval_seconds: float = 7.5) -> None:
        self.interval_seconds = interval_seconds
        self.tick_calls: list[str] = []

        async def tick_callback(run_id: str) -> None:
            self.tick_calls.append(run_id)

        self.tick_callback = tick_callback


class FakeBootstrapper:
    def __init__(self, plan: FakePlan) -> None:
        self.plan = plan
        self.prepare_calls: list[str] = []

    async def prepare(self, session, run):
        self.prepare_calls.append(run.id)
        return self.plan


@pytest.mark.asyncio
async def test_ensure_run_started_updates_status_when_scheduler_already_running(db_session):
    run = SimulationRun(id="run-lifecycle-1", name="demo", status="paused")
    db_session.add(run)
    await db_session.commit()

    scheduler = FakeScheduler(running=True)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(run_lifecycle_module, "get_scheduler", lambda: scheduler)
    try:
        updated = await run_lifecycle_module.ensure_run_started(db_session, run)
    finally:
        monkeypatch.undo()

    refreshed = await RunRepository(db_session).get("run-lifecycle-1")
    assert updated.status == "running"
    assert refreshed is not None
    assert refreshed.status == "running"
    assert scheduler.started == []


@pytest.mark.asyncio
async def test_ensure_run_started_warms_pool_and_registers_tick_callback(db_session, tmp_path):
    run = SimulationRun(
        id="run-lifecycle-2",
        name="demo",
        status="draft",
        scenario_type="truman_world",
    )
    db_session.add_all(
        [
            run,
            Agent(
                id="run-lifecycle-2-alice",
                run_id="run-lifecycle-2",
                name="Alice",
                occupation="barista",
                profile={"agent_config_id": "spouse"},
                personality={},
                status={},
                current_plan={},
            ),
            Agent(
                id="run-lifecycle-2-bob",
                run_id="run-lifecycle-2",
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

    scheduler = FakeScheduler(running=False)
    plan = FakePlan(interval_seconds=7.5)
    bootstrapper = FakeBootstrapper(plan)

    class FakeBootstrapperFactory:
        def __call__(self):
            return bootstrapper

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(run_lifecycle_module, "get_scheduler", lambda: scheduler)
    monkeypatch.setattr(run_lifecycle_module, "RunExecutionBootstrapper", FakeBootstrapperFactory())
    try:
        updated = await run_lifecycle_module.ensure_run_started(db_session, run)
        callback = scheduler.started[0][2]
        await callback("run-lifecycle-2")
    finally:
        monkeypatch.undo()

    assert updated.status == "running"
    assert bootstrapper.prepare_calls == ["run-lifecycle-2"]
    assert scheduler.started
    assert scheduler.started[0][0] == "run-lifecycle-2"
    assert scheduler.started[0][1] == 7.5
    assert plan.tick_calls == ["run-lifecycle-2"]


@pytest.mark.asyncio
async def test_ensure_run_started_skips_warmup_when_run_has_no_agents(db_session, tmp_path):
    run = SimulationRun(id="run-lifecycle-3", name="demo", status="draft")
    db_session.add(run)
    await db_session.commit()

    scheduler = FakeScheduler(running=False)
    bootstrapper = FakeBootstrapper(FakePlan(interval_seconds=3.0))

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(run_lifecycle_module, "get_scheduler", lambda: scheduler)
    monkeypatch.setattr(run_lifecycle_module, "RunExecutionBootstrapper", lambda: bootstrapper)
    try:
        await run_lifecycle_module.ensure_run_started(db_session, run)
    finally:
        monkeypatch.undo()

    assert bootstrapper.prepare_calls == ["run-lifecycle-3"]
    assert len(scheduler.started) == 1


@pytest.mark.asyncio
async def test_pause_run_execution_stops_scheduler_and_cleans_pool():
    scheduler = FakeScheduler(running=True)
    cognition_registry = FakeCognitionRegistry()

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(run_lifecycle_module, "get_scheduler", lambda: scheduler)
    monkeypatch.setattr(
        run_lifecycle_module,
        "get_cognition_registry",
        lambda: cognition_registry,
    )
    try:
        await run_lifecycle_module.pause_run_execution("run-lifecycle-4")
    finally:
        monkeypatch.undo()

    assert scheduler.stopped == ["run-lifecycle-4"]
    assert cognition_registry.cleanup_calls == ["run-lifecycle-4"]


@pytest.mark.asyncio
async def test_pause_run_execution_skips_pool_cleanup_when_reactor_pool_disabled():
    scheduler = FakeScheduler(running=True)
    cognition_registry = FakeCognitionRegistry(cleanup_result=0)

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(run_lifecycle_module, "get_scheduler", lambda: scheduler)
    monkeypatch.setattr(
        run_lifecycle_module,
        "get_cognition_registry",
        lambda: cognition_registry,
    )
    try:
        await run_lifecycle_module.pause_run_execution("run-lifecycle-5")
    finally:
        monkeypatch.undo()

    assert scheduler.stopped == ["run-lifecycle-5"]
    assert cognition_registry.cleanup_calls == ["run-lifecycle-5"]
