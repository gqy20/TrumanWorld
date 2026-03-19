import asyncio
from datetime import datetime, timezone
from pathlib import Path
import shutil
import tempfile

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.agent.registry import AgentRegistry
from app.agent.runtime import AgentRuntime, RuntimeInvocation
from app.cognition.claude.decision_provider import AgentDecisionProvider
from app.cognition.claude.decision_utils import RuntimeDecision
from app.cognition.errors import UpstreamApiUnavailableError
from app.cognition.heuristic.agent_backend import HeuristicAgentBackend
from app.scenario.types import ScenarioGuidance
from app.sim.action_resolver import ActionIntent
from app.sim.context import get_run_world_time
from app.sim.service import SimulationService
from app.sim.tick_orchestrator import TickOrchestrator
from app.sim.types import AgentDecisionSnapshot
from app.sim.world import WorldState
from app.store.models import Agent, Base, Location, SimulationRun
from app.store.repositories import EventRepository, LlmCallRepository, RunRepository

from .test_service import FakeScenario, MixedOutcomeDecisionProvider


class TokenCapturingDecisionProvider(AgentDecisionProvider):
    def __init__(self, usage: dict | None = None, cost: float = 0.01) -> None:
        self.captured_ctx: list = []
        self.captured_invocations: list[RuntimeInvocation] = []
        self._usage = usage or {"input_tokens": 100, "output_tokens": 200}
        self._cost = cost

    async def decide(self, invocation: RuntimeInvocation, runtime_ctx=None):
        self.captured_ctx.append(runtime_ctx)
        self.captured_invocations.append(invocation)
        if runtime_ctx and runtime_ctx.on_llm_call:
            runtime_ctx.on_llm_call(
                agent_id=invocation.agent_id,
                task_type=invocation.task,
                usage=self._usage,
                total_cost_usd=self._cost,
                duration_ms=500,
            )
        return RuntimeDecision(action_type="rest")


@pytest.mark.asyncio
async def test_run_tick_isolated_with_separate_sessions(db_session):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    run_id = "run-isolated-1"
    async with AsyncSession(engine, expire_on_commit=False) as session:
        run = SimulationRun(
            id=run_id, name="isolated", status="running", current_tick=0, tick_minutes=5
        )
        home = Location(
            id="loc-home-isolated", run_id=run_id, name="Home", location_type="home", capacity=2
        )
        alice = Agent(
            id="alice-isolated",
            run_id=run_id,
            name="Alice",
            occupation="resident",
            home_location_id="loc-home-isolated",
            current_location_id="loc-home-isolated",
            personality={},
            profile={},
            status={},
            current_plan={},
        )
        session.add_all([run, home, alice])
        await session.commit()

    tmp_path = Path(tempfile.mkdtemp())
    agent_dir = tmp_path / "agent"
    agent_dir.mkdir()
    (agent_dir / "agent.yml").write_text("id: test\nname: Test\noccupation: test\nhome: home\n")
    (agent_dir / "prompt.md").write_text("# Test")

    runtime = AgentRuntime(registry=AgentRegistry(tmp_path), backend=HeuristicAgentBackend())
    service = SimulationService.create_for_scheduler(runtime)

    result = await service.run_tick_isolated(
        run_id,
        engine,
        [ActionIntent(agent_id="alice-isolated", action_type="rest")],
    )

    assert result.tick_no == 1
    assert len(result.accepted) == 1
    assert result.accepted[0].action_type == "rest"

    async with AsyncSession(engine, expire_on_commit=False) as session:
        updated_run = await RunRepository(session).get(run_id)
        assert updated_run is not None
        assert updated_run.current_tick == 1

    await engine.dispose()
    shutil.rmtree(tmp_path)


@pytest.mark.asyncio
async def test_run_tick_isolated_skips_sleep_hours_and_persists_advanced_tick(db_session):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    run_id = "run-isolated-sleep-skip"
    async with AsyncSession(engine, expire_on_commit=False) as session:
        run = SimulationRun(
            id=run_id,
            name="isolated-sleep-skip",
            status="running",
            current_tick=203,
            tick_minutes=5,
        )
        home = Location(
            id="loc-home-sleep-skip",
            run_id=run_id,
            name="Home",
            location_type="home",
            capacity=2,
        )
        alice = Agent(
            id="alice-sleep-skip",
            run_id=run_id,
            name="Alice",
            occupation="resident",
            home_location_id="loc-home-sleep-skip",
            current_location_id="loc-home-sleep-skip",
            personality={},
            profile={},
            status={},
            current_plan={},
        )
        session.add_all([run, home, alice])
        await session.commit()

    tmp_path = Path(tempfile.mkdtemp())
    agent_dir = tmp_path / "agent"
    agent_dir.mkdir()
    (agent_dir / "agent.yml").write_text("id: test\nname: Test\noccupation: test\nhome: home\n")
    (agent_dir / "prompt.md").write_text("# Test")

    runtime = AgentRuntime(registry=AgentRegistry(tmp_path), backend=HeuristicAgentBackend())
    service = SimulationService.create_for_scheduler(runtime)

    result = await service.run_tick_isolated(
        run_id,
        engine,
        [ActionIntent(agent_id="alice-sleep-skip", action_type="rest")],
    )

    assert result.tick_delta == 85
    assert result.tick_no == 288
    assert result.world_time == "2026-03-03T06:00:00+00:00"

    async with AsyncSession(engine, expire_on_commit=False) as session:
        updated_run = await RunRepository(session).get(run_id)
        assert updated_run is not None
        assert updated_run.current_tick == 288
        assert get_run_world_time(updated_run).isoformat() == "2026-03-03T06:00:00+00:00"

    await engine.dispose()
    shutil.rmtree(tmp_path)


@pytest.mark.asyncio
async def test_prepare_intents_collects_llm_records_when_on_llm_call_set(db_session):
    run_id = "run-token-track-1"
    run = SimulationRun(
        id=run_id, name="token-track", status="running", current_tick=3, tick_minutes=5
    )
    agent = Agent(
        id="agent-tt-1",
        run_id=run_id,
        name="Alice",
        occupation="resident",
        personality={},
        profile={},
        status={},
        current_plan={},
    )
    db_session.add_all([run, agent])
    await db_session.commit()

    tmp_path = Path(tempfile.mkdtemp())
    agent_dir = tmp_path / "agent-tt-1"
    agent_dir.mkdir(parents=True)
    (agent_dir / "agent.yml").write_text(
        "id: agent-tt-1\nname: Alice\noccupation: resident\nhome: loc-1\n",
        encoding="utf-8",
    )
    (agent_dir / "prompt.md").write_text("# Alice\nBase prompt", encoding="utf-8")
    provider = TokenCapturingDecisionProvider(
        usage={"input_tokens": 130, "output_tokens": 250, "cache_read_input_tokens": 60},
        cost=0.025,
    )
    runtime = AgentRuntime(
        registry=AgentRegistry(tmp_path),
        backend=HeuristicAgentBackend(provider),
    )
    orchestrator = TickOrchestrator(agent_runtime=runtime, scenario=FakeScenario())

    world = WorldState(current_time=datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc))
    world.agents["agent-tt-1"] = type(
        "S", (), {"id": "agent-tt-1", "status": {}, "location_id": "loc-1"}
    )()
    snapshot = AgentDecisionSnapshot(
        id="agent-tt-1",
        current_goal="rest",
        current_location_id="loc-1",
        home_location_id="loc-1",
        profile={},
        recent_events=[],
    )

    intents, llm_records = await orchestrator.prepare_intents_from_data(
        world=world,
        agent_data=[snapshot],
        engine=None,
        run_id=run_id,
        tick_no=3,
    )

    assert len(llm_records) == 1
    assert llm_records[0].input_tokens == 130
    assert len(intents) == 1
    assert provider.captured_invocations[0].context["world"]["subject_alert_score"] == 0.0
    assert (
        provider.captured_invocations[0].context["world"]["truman_suspicion_score"]
        == provider.captured_invocations[0].context["world"]["subject_alert_score"]
    )

    shutil.rmtree(tmp_path)


class UnavailableApiBackend:
    async def decide_action(self, invocation, runtime_ctx=None):
        raise UpstreamApiUnavailableError("rate_limit_error")

    async def plan_day(self, invocation, runtime_ctx=None):
        return None

    async def reflect_day(self, invocation, runtime_ctx=None):
        return None


@pytest.mark.asyncio
async def test_prepare_intents_from_data_raises_on_upstream_api_unavailable(db_session):
    tmp_path = Path(tempfile.mkdtemp())
    agent_dir = tmp_path / "agent-stop-fast"
    agent_dir.mkdir(parents=True)
    (agent_dir / "agent.yml").write_text(
        "id: agent-stop-fast\nname: Alice\noccupation: resident\nhome: loc-1\n",
        encoding="utf-8",
    )
    (agent_dir / "prompt.md").write_text("# Alice\nBase prompt", encoding="utf-8")

    runtime = AgentRuntime(
        registry=AgentRegistry(tmp_path),
        backend=UnavailableApiBackend(),
    )
    orchestrator = TickOrchestrator(agent_runtime=runtime, scenario=FakeScenario())

    world = WorldState(current_time=datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc))
    world.agents["agent-stop-fast"] = type(
        "S", (), {"id": "agent-stop-fast", "status": {}, "location_id": "loc-1"}
    )()
    snapshot = AgentDecisionSnapshot(
        id="agent-stop-fast",
        current_goal="rest",
        current_location_id="loc-1",
        home_location_id="loc-1",
        profile={},
        recent_events=[],
    )

    with pytest.raises(UpstreamApiUnavailableError):
        await orchestrator.prepare_intents_from_data(
            world=world,
            agent_data=[snapshot],
            engine=None,
            run_id="run-stop-fast",
            tick_no=3,
        )

    shutil.rmtree(tmp_path)


@pytest.mark.asyncio
async def test_prepare_intents_from_data_respects_runtime_concurrency_limit(db_session):
    run_id = "run-concurrency-limit-1"
    run = SimulationRun(
        id=run_id, name="concurrency-limit", status="running", current_tick=1, tick_minutes=5
    )
    agents = [
        Agent(
            id=f"agent-limit-{i}",
            run_id=run_id,
            name=f"Agent {i}",
            occupation="resident",
            personality={},
            profile={},
            status={},
            current_plan={},
        )
        for i in range(3)
    ]
    db_session.add(run)
    db_session.add_all(agents)
    await db_session.commit()

    tmp_path = Path(tempfile.mkdtemp())
    try:
        for agent in agents:
            agent_dir = tmp_path / agent.id
            agent_dir.mkdir(parents=True)
            (agent_dir / "agent.yml").write_text(
                f"id: {agent.id}\nname: {agent.name}\noccupation: resident\nhome: loc-1\n",
                encoding="utf-8",
            )
            (agent_dir / "prompt.md").write_text("# Prompt\nBase prompt", encoding="utf-8")

        class SlowProvider(AgentDecisionProvider):
            def __init__(self) -> None:
                self.in_flight = 0
                self.max_in_flight = 0

            async def decide(self, invocation: RuntimeInvocation, runtime_ctx=None):
                self.in_flight += 1
                self.max_in_flight = max(self.max_in_flight, self.in_flight)
                try:
                    await asyncio.sleep(0.05)
                    return RuntimeDecision(action_type="rest")
                finally:
                    self.in_flight -= 1

        class LimitedBackend(HeuristicAgentBackend):
            def __init__(self, provider: AgentDecisionProvider) -> None:
                super().__init__(provider)

            def decision_concurrency_limit(self) -> int:
                return 1

        provider = SlowProvider()
        runtime = AgentRuntime(
            registry=AgentRegistry(tmp_path),
            backend=LimitedBackend(provider),
        )
        orchestrator = TickOrchestrator(agent_runtime=runtime, scenario=FakeScenario())

        world = WorldState(current_time=datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc))
        snapshots: list[AgentDecisionSnapshot] = []
        for agent in agents:
            world.agents[agent.id] = type(
                "S", (), {"id": agent.id, "status": {}, "location_id": "loc-1"}
            )()
            snapshots.append(
                AgentDecisionSnapshot(
                    id=agent.id,
                    current_goal="rest",
                    current_location_id="loc-1",
                    home_location_id="loc-1",
                    profile={},
                    recent_events=[],
                )
            )

        intents, _ = await orchestrator.prepare_intents_from_data(
            world=world,
            agent_data=snapshots,
            engine=None,
            run_id=run_id,
            tick_no=1,
        )

        assert len(intents) == 3
        assert provider.max_in_flight == 1
    finally:
        shutil.rmtree(tmp_path)


@pytest.mark.asyncio
async def test_prepare_intents_from_data_uses_scenario_fallback_for_failed_agent(db_session):
    run_id = "run-fallback-per-agent-1"
    run = SimulationRun(id=run_id, name="fallback-per-agent", status="running", current_tick=1)
    agents = [
        Agent(
            id="agent-fallback-ok",
            run_id=run_id,
            name="Agent OK",
            occupation="resident",
            personality={},
            profile={},
            status={},
            current_plan={},
        ),
        Agent(
            id="agent-fallback-bad",
            run_id=run_id,
            name="Agent Bad",
            occupation="resident",
            personality={},
            profile={},
            status={},
            current_plan={},
        ),
    ]
    db_session.add(run)
    db_session.add_all(agents)
    await db_session.commit()

    tmp_path = Path(tempfile.mkdtemp())
    try:
        for agent in agents:
            agent_dir = tmp_path / agent.id
            agent_dir.mkdir(parents=True)
            (agent_dir / "agent.yml").write_text(
                f"id: {agent.id}\nname: {agent.name}\noccupation: resident\nhome: loc-1\n",
                encoding="utf-8",
            )
            (agent_dir / "prompt.md").write_text("# Prompt\nBase prompt", encoding="utf-8")

        provider = MixedOutcomeDecisionProvider(failing_agent_ids={"agent-fallback-bad"})
        runtime = AgentRuntime(
            registry=AgentRegistry(tmp_path),
            backend=HeuristicAgentBackend(provider),
        )

        class FallbackScenario(FakeScenario):
            def fallback_intent(
                self,
                *,
                agent_id: str,
                current_location_id: str,
                home_location_id: str | None,
                nearby_agent_id: str | None,
                world_role: str | None = None,
                current_status: dict | None = None,
                scenario_state: dict | None = None,
                scenario_guidance: ScenarioGuidance | None = None,
            ):
                return ActionIntent(
                    agent_id=agent_id,
                    action_type="move",
                    target_location_id=home_location_id or current_location_id,
                )

        orchestrator = TickOrchestrator(agent_runtime=runtime, scenario=FallbackScenario())

        world = WorldState(current_time=datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc))
        snapshots: list[AgentDecisionSnapshot] = []
        for agent in agents:
            world.agents[agent.id] = type(
                "S", (), {"id": agent.id, "status": {}, "location_id": "loc-1"}
            )()
            snapshots.append(
                AgentDecisionSnapshot(
                    id=agent.id,
                    current_goal="rest",
                    current_location_id="loc-1",
                    home_location_id="loc-home",
                    profile={},
                    recent_events=[],
                )
            )

        intents, llm_records = await orchestrator.prepare_intents_from_data(
            world=world,
            agent_data=snapshots,
            engine=None,
            run_id=run_id,
            tick_no=1,
        )

        intents_by_agent = {intent.agent_id: intent for intent in intents}
        assert len(intents) == 2
        assert llm_records == []
        assert intents_by_agent["agent-fallback-ok"].action_type == "work"
        assert intents_by_agent["agent-fallback-bad"].action_type == "move"
        assert intents_by_agent["agent-fallback-bad"].target_location_id == "loc-home"
    finally:
        shutil.rmtree(tmp_path)


@pytest.mark.asyncio
async def test_run_tick_isolated_persists_llm_calls(db_session):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    run_id = "run-llm-persist-1"
    agent_config_id = "alice-llm"
    async with AsyncSession(engine, expire_on_commit=False) as session:
        run = SimulationRun(
            id=run_id, name="llm-persist", status="running", current_tick=0, tick_minutes=5
        )
        loc = Location(id="loc-llm-1", run_id=run_id, name="Home", location_type="home", capacity=2)
        agent = Agent(
            id="agent-llm-p1",
            run_id=run_id,
            name="Alice",
            occupation="resident",
            home_location_id="loc-llm-1",
            current_location_id="loc-llm-1",
            personality={},
            profile={"agent_config_id": agent_config_id},
            status={},
            current_plan={},
        )
        session.add_all([run, loc, agent])
        await session.commit()

    tmp_path = Path(tempfile.mkdtemp())
    agent_dir = tmp_path / agent_config_id
    agent_dir.mkdir(parents=True)
    (agent_dir / "agent.yml").write_text(
        f"id: {agent_config_id}\nname: Alice\noccupation: resident\nhome: loc-llm-1\n",
        encoding="utf-8",
    )
    (agent_dir / "prompt.md").write_text("# Alice\nBase prompt", encoding="utf-8")

    provider = TokenCapturingDecisionProvider(
        usage={"input_tokens": 111, "output_tokens": 222, "cache_read_input_tokens": 33},
        cost=0.015,
    )
    runtime = AgentRuntime(
        registry=AgentRegistry(tmp_path), backend=HeuristicAgentBackend(provider)
    )
    service = SimulationService.create_for_scheduler(runtime)

    result = await service.run_tick_isolated(run_id, engine)

    assert result.tick_no == 1

    async with AsyncSession(engine, expire_on_commit=False) as session:
        totals = await LlmCallRepository(session).get_token_totals(run_id)
        assert totals["input_tokens"] == 111
        assert totals["output_tokens"] == 222
        assert totals["cache_read_tokens"] == 33

    await engine.dispose()
    shutil.rmtree(tmp_path)


@pytest.mark.asyncio
async def test_run_tick_isolated_advances_when_one_agent_falls_back():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    run_id = "run-isolated-fallback-1"
    async with AsyncSession(engine, expire_on_commit=False) as session:
        run = SimulationRun(
            id=run_id,
            name="isolated-fallback",
            status="running",
            current_tick=0,
            tick_minutes=5,
            scenario_type="truman_world",
        )
        home = Location(id="loc-home-fb", run_id=run_id, name="Home", location_type="home", capacity=4)
        office = Location(
            id="loc-office-fb",
            run_id=run_id,
            name="Office",
            location_type="office",
            capacity=4,
        )
        ok_agent = Agent(
            id="agent-fallback-ok-iso",
            run_id=run_id,
            name="Alice",
            occupation="resident",
            home_location_id=home.id,
            current_location_id=office.id,
            personality={},
            profile={"agent_config_id": "agent-fallback-ok-iso", "world_role": "cast"},
            status={},
            current_plan={},
        )
        bad_agent = Agent(
            id="agent-fallback-bad-iso",
            run_id=run_id,
            name="Bob",
            occupation="resident",
            home_location_id=home.id,
            current_location_id=office.id,
            personality={},
            profile={"agent_config_id": "agent-fallback-bad-iso", "world_role": "cast"},
            status={},
            current_plan={},
        )
        session.add_all([run, home, office, ok_agent, bad_agent])
        await session.commit()

    tmp_path = Path(tempfile.mkdtemp())
    try:
        for agent_id, name in (
            ("agent-fallback-ok-iso", "Alice"),
            ("agent-fallback-bad-iso", "Bob"),
        ):
            agent_dir = tmp_path / agent_id
            agent_dir.mkdir(parents=True)
            (agent_dir / "agent.yml").write_text(
                f"id: {agent_id}\nname: {name}\noccupation: resident\nhome: loc-home-fb\n",
                encoding="utf-8",
            )
            (agent_dir / "prompt.md").write_text(f"# {name}\nBase prompt", encoding="utf-8")

        provider = MixedOutcomeDecisionProvider(
            failing_agent_ids={"agent-fallback-bad-iso"},
            success_action="work",
        )
        runtime = AgentRuntime(
            registry=AgentRegistry(tmp_path),
            backend=HeuristicAgentBackend(provider),
        )
        service = SimulationService.create_for_scheduler(runtime)

        result = await service.run_tick_isolated(run_id, engine)

        assert result.tick_no == 1
        assert any(item.action_type == "talk" for item in result.accepted)
        assert len(result.rejected) == 1

        async with AsyncSession(engine, expire_on_commit=False) as session:
            updated_run = await RunRepository(session).get(run_id)
            events = await EventRepository(session).list_for_run(run_id)
            assert updated_run is not None
            assert updated_run.current_tick == 1
            event_types = {event.event_type for event in events}
            assert "speech" in event_types
            assert "conversation_started" in event_types
            assert any(event.event_type.endswith("_rejected") for event in events)
    finally:
        await engine.dispose()
        shutil.rmtree(tmp_path)
