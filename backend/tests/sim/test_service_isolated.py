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
from app.infra.settings import get_settings
from app.scenario.types import ScenarioGuidance
from app.sim.action_resolver import ActionIntent
from app.sim.context import get_run_world_time
from app.sim.service import SimulationService
from app.sim.tick_orchestrator import TickOrchestrator
from app.sim.types import AgentDecisionSnapshot
from app.sim.world import AgentState, LocationState, WorldState
from app.store.models import Base
from app.store.repositories import EventRepository, LlmCallRepository, RunRepository
from tests.factories import make_agent, make_location, make_run, write_agent_config

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


class FixedTalkDecisionProvider(TokenCapturingDecisionProvider):
    def __init__(self, *, message: str, target_agent_id: str) -> None:
        super().__init__()
        self._message = message
        self._target_agent_id = target_agent_id

    async def decide(self, invocation: RuntimeInvocation, runtime_ctx=None):
        await super().decide(invocation, runtime_ctx=runtime_ctx)
        return RuntimeDecision(
            action_type="talk",
            target_agent_id=self._target_agent_id,
            message=self._message,
        )


@pytest.mark.asyncio
async def test_run_tick_isolated_with_separate_sessions(db_session):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    run_id = "run-isolated-1"
    async with AsyncSession(engine, expire_on_commit=False) as session:
        run = make_run(run_id, name="isolated")
        home = make_location("loc-home-isolated", run_id=run_id, name="Home", location_type="home")
        alice = make_agent(
            "alice-isolated",
            run_id=run_id,
            location_id="loc-home-isolated",
            name="Alice",
        )
        session.add_all([run, home, alice])
        await session.commit()

    tmp_path = Path(tempfile.mkdtemp())
    write_agent_config(tmp_path, "agent", name="Test", occupation="test")

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
        run = make_run(
            run_id,
            name="isolated-sleep-skip",
            current_tick=203,
        )
        home = make_location(
            "loc-home-sleep-skip",
            run_id=run_id,
            name="Home",
            location_type="home",
        )
        alice = make_agent(
            "alice-sleep-skip",
            run_id=run_id,
            location_id="loc-home-sleep-skip",
            name="Alice",
        )
        session.add_all([run, home, alice])
        await session.commit()

    tmp_path = Path(tempfile.mkdtemp())
    write_agent_config(tmp_path, "agent", name="Test", occupation="test")

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
    run = make_run(run_id, name="token-track", current_tick=3)
    agent = make_agent(
        "agent-tt-1",
        run_id=run_id,
        name="Alice",
    )
    db_session.add_all([run, agent])
    await db_session.commit()

    tmp_path = Path(tempfile.mkdtemp())
    write_agent_config(tmp_path, "agent-tt-1", name="Alice", home="loc-1")
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
    assert "truman_suspicion_score" not in provider.captured_invocations[0].context["world"]

    shutil.rmtree(tmp_path)


@pytest.mark.asyncio
async def test_prepare_intents_from_data_biases_rest_to_reply_for_recent_question():
    tmp_path = Path(tempfile.mkdtemp())
    try:
        agent_dir = tmp_path / "agent-reply"
        agent_dir.mkdir(parents=True)
        (agent_dir / "agent.yml").write_text(
            "id: agent-reply\nname: Alice\noccupation: resident\nhome: loc-1\n",
            encoding="utf-8",
        )
        (agent_dir / "prompt.md").write_text("# Alice\nBase prompt", encoding="utf-8")

        provider = TokenCapturingDecisionProvider()
        runtime = AgentRuntime(
            registry=AgentRegistry(tmp_path),
            backend=HeuristicAgentBackend(provider),
        )
        orchestrator = TickOrchestrator(agent_runtime=runtime, scenario=FakeScenario())

        world = WorldState(current_time=datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc))
        world.current_tick = 6
        world.locations["loc-1"] = LocationState(
            id="loc-1",
            name="Dorm",
            location_type="home",
            occupants={"alice", "bob"},
        )
        world.agents["alice"] = AgentState(
            id="alice",
            name="Alice",
            location_id="loc-1",
            occupation="resident",
            workplace_id=None,
            status={},
        )
        world.agents["bob"] = AgentState(
            id="bob",
            name="Bob",
            location_id="loc-1",
            occupation="friend",
            workplace_id=None,
            status={},
        )
        snapshot = AgentDecisionSnapshot(
            id="alice",
            current_goal="rest",
            current_location_id="loc-1",
            home_location_id="loc-1",
            profile={"agent_config_id": "agent-reply"},
            recent_events=[
                {
                    "event_type": "speech",
                    "tick_no": 5,
                    "actor_agent_id": "bob",
                    "actor_name": "Bob",
                    "target_agent_id": "alice",
                    "message": "要不要一起去咖啡馆？",
                }
            ],
        )

        intents, _ = await orchestrator.prepare_intents_from_data(
            world=world,
            agent_data=[snapshot],
            engine=None,
            run_id="run-pending-reply",
            tick_no=6,
        )

        assert len(intents) == 1
        assert intents[0].action_type == "talk"
        assert intents[0].target_agent_id == "bob"
        assert intents[0].payload["intent_source"] == "pending_reply_bias"
        assert (
            provider.captured_invocations[0].context["world"]["pending_reply"]["from_agent_id"]
            == "bob"
        )
    finally:
        shutil.rmtree(tmp_path)


@pytest.mark.asyncio
async def test_prepare_intents_from_data_keeps_rest_for_closing_message():
    tmp_path = Path(tempfile.mkdtemp())
    try:
        agent_dir = tmp_path / "agent-closing"
        agent_dir.mkdir(parents=True)
        (agent_dir / "agent.yml").write_text(
            "id: agent-closing\nname: Alice\noccupation: resident\nhome: loc-1\n",
            encoding="utf-8",
        )
        (agent_dir / "prompt.md").write_text("# Alice\nBase prompt", encoding="utf-8")

        provider = TokenCapturingDecisionProvider()
        runtime = AgentRuntime(
            registry=AgentRegistry(tmp_path),
            backend=HeuristicAgentBackend(provider),
        )
        orchestrator = TickOrchestrator(agent_runtime=runtime, scenario=FakeScenario())

        world = WorldState(current_time=datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc))
        world.current_tick = 6
        world.locations["loc-1"] = LocationState(
            id="loc-1",
            name="Dorm",
            location_type="home",
            occupants={"alice", "bob"},
        )
        world.agents["alice"] = AgentState(
            id="alice",
            name="Alice",
            location_id="loc-1",
            occupation="resident",
            workplace_id=None,
            status={},
        )
        world.agents["bob"] = AgentState(
            id="bob",
            name="Bob",
            location_id="loc-1",
            occupation="friend",
            workplace_id=None,
            status={},
        )
        snapshot = AgentDecisionSnapshot(
            id="alice",
            current_goal="rest",
            current_location_id="loc-1",
            home_location_id="loc-1",
            profile={"agent_config_id": "agent-closing"},
            recent_events=[
                {
                    "event_type": "speech",
                    "tick_no": 5,
                    "actor_agent_id": "bob",
                    "actor_name": "Bob",
                    "target_agent_id": "alice",
                    "message": "那你先忙，下午见。",
                }
            ],
        )

        intents, _ = await orchestrator.prepare_intents_from_data(
            world=world,
            agent_data=[snapshot],
            engine=None,
            run_id="run-closing-reply",
            tick_no=6,
        )

        assert len(intents) == 1
        assert intents[0].action_type == "rest"
        assert "pending_reply" not in provider.captured_invocations[0].context["world"]
    finally:
        shutil.rmtree(tmp_path)


@pytest.mark.asyncio
async def test_prepare_intents_from_data_suppresses_repeated_conversation_proposal():
    tmp_path = Path(tempfile.mkdtemp())
    try:
        agent_dir = tmp_path / "agent-repeat"
        agent_dir.mkdir(parents=True)
        (agent_dir / "agent.yml").write_text(
            "id: agent-repeat\nname: Alice\noccupation: resident\nhome: loc-1\n",
            encoding="utf-8",
        )
        (agent_dir / "prompt.md").write_text("# Alice\nBase prompt", encoding="utf-8")

        provider = FixedTalkDecisionProvider(
            message="要不要一起去咖啡馆？",
            target_agent_id="bob",
        )
        runtime = AgentRuntime(
            registry=AgentRegistry(tmp_path),
            backend=HeuristicAgentBackend(provider),
        )
        orchestrator = TickOrchestrator(agent_runtime=runtime, scenario=FakeScenario())

        world = WorldState(current_time=datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc))
        world.current_tick = 6
        world.locations["loc-1"] = LocationState(
            id="loc-1",
            name="Dorm",
            location_type="home",
            occupants={"alice", "bob"},
        )
        world.agents["alice"] = AgentState(
            id="alice",
            name="Alice",
            location_id="loc-1",
            occupation="resident",
            workplace_id=None,
            status={},
        )
        world.agents["bob"] = AgentState(
            id="bob",
            name="Bob",
            location_id="loc-1",
            occupation="friend",
            workplace_id=None,
            status={},
        )
        world.active_conversations = {
            "conv-1": type(
                "ConversationState",
                (),
                {
                    "id": "conv-1",
                    "location_id": "loc-1",
                    "participant_ids": ["alice", "bob"],
                    "active_speaker_id": "alice",
                    "last_tick_no": 5,
                    "last_message_summary": "要不要一起去咖啡馆？",
                    "last_proposal": "要不要一起去咖啡馆？",
                    "open_question": "要不要一起去咖啡馆？",
                    "repeat_count": 2,
                },
            )()
        }

        snapshot = AgentDecisionSnapshot(
            id="alice",
            current_goal="talk",
            current_location_id="loc-1",
            home_location_id="loc-1",
            profile={"agent_config_id": "agent-repeat"},
            recent_events=[],
        )

        intents, _ = await orchestrator.prepare_intents_from_data(
            world=world,
            agent_data=[snapshot],
            engine=None,
            run_id="run-repeat-guard",
            tick_no=6,
        )

        assert len(intents) == 1
        assert intents[0].action_type == "rest"
        assert intents[0].payload["intent_source"] == "conversation_repeat_guard"
        assert (
            provider.captured_invocations[0].context["world"]["conversation_state"]["repeat_count"]
            == 2
        )
    finally:
        shutil.rmtree(tmp_path)


@pytest.mark.asyncio
async def test_prepare_intents_from_data_suppresses_high_overlap_paraphrase_proposal():
    tmp_path = Path(tempfile.mkdtemp())
    try:
        agent_dir = tmp_path / "agent-repeat-paraphrase"
        agent_dir.mkdir(parents=True)
        (agent_dir / "agent.yml").write_text(
            "id: agent-repeat-paraphrase\nname: Alice\noccupation: resident\nhome: loc-1\n",
            encoding="utf-8",
        )
        (agent_dir / "prompt.md").write_text("# Alice\nBase prompt", encoding="utf-8")

        provider = FixedTalkDecisionProvider(
            message=(
                "好，那咱们就分头行动。我这就去把图表数据整理好发给你，"
                "你那边先搭好核心论点的大纲，等陈教授有空你再去请教一下。"
            ),
            target_agent_id="bob",
        )
        runtime = AgentRuntime(
            registry=AgentRegistry(tmp_path),
            backend=HeuristicAgentBackend(provider),
        )
        orchestrator = TickOrchestrator(agent_runtime=runtime, scenario=FakeScenario())

        world = WorldState(current_time=datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc))
        world.current_tick = 6
        world.locations["loc-1"] = LocationState(
            id="loc-1",
            name="Dorm",
            location_type="home",
            occupants={"alice", "bob"},
        )
        world.agents["alice"] = AgentState(
            id="alice",
            name="Alice",
            location_id="loc-1",
            occupation="resident",
            workplace_id=None,
            status={},
        )
        world.agents["bob"] = AgentState(
            id="bob",
            name="Bob",
            location_id="loc-1",
            occupation="friend",
            workplace_id=None,
            status={},
        )
        world.active_conversations = {
            "conv-1": type(
                "ConversationState",
                (),
                {
                    "id": "conv-1",
                    "location_id": "loc-1",
                    "participant_ids": ["alice", "bob"],
                    "active_speaker_id": "alice",
                    "last_tick_no": 5,
                    "last_message_summary": (
                        "行，那就这么定了。陈教授在附近确实得低调点，"
                        "我这就去把图表数据整理好发给你，你那边先搭好核心论点的大纲。"
                    ),
                    "last_proposal": (
                        "行，那就这么定了。陈教授在附近确实得低调点，"
                        "我这就去把图表数据整理好发给你，你那边先搭好核心论点的大纲。"
                    ),
                    "open_question": None,
                    "repeat_count": 1,
                },
            )()
        }

        snapshot = AgentDecisionSnapshot(
            id="alice",
            current_goal="talk",
            current_location_id="loc-1",
            home_location_id="loc-1",
            profile={"agent_config_id": "agent-repeat-paraphrase"},
            recent_events=[],
        )

        intents, _ = await orchestrator.prepare_intents_from_data(
            world=world,
            agent_data=[snapshot],
            engine=None,
            run_id="run-repeat-paraphrase-guard",
            tick_no=6,
        )

        assert len(intents) == 1
        assert intents[0].action_type == "rest"
        assert intents[0].payload["intent_source"] == "conversation_repeat_guard"
    finally:
        shutil.rmtree(tmp_path)


@pytest.mark.asyncio
async def test_prepare_intents_from_data_prefers_recent_conversation_partner_over_sorted_occupant():
    tmp_path = Path(tempfile.mkdtemp())
    try:
        agent_dir = tmp_path / "agent-partner"
        agent_dir.mkdir(parents=True)
        (agent_dir / "agent.yml").write_text(
            "id: agent-partner\nname: Alice\noccupation: resident\nhome: loc-1\n",
            encoding="utf-8",
        )
        (agent_dir / "prompt.md").write_text("# Alice\nBase prompt", encoding="utf-8")

        provider = TokenCapturingDecisionProvider()
        runtime = AgentRuntime(
            registry=AgentRegistry(tmp_path),
            backend=HeuristicAgentBackend(provider),
        )
        orchestrator = TickOrchestrator(agent_runtime=runtime, scenario=FakeScenario())

        world = WorldState(current_time=datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc))
        world.current_tick = 8
        world.locations["loc-1"] = LocationState(
            id="loc-1",
            name="Dorm",
            location_type="home",
            occupants={"alice", "bob", "aaron"},
        )
        world.agents["alice"] = AgentState(
            id="alice",
            name="Alice",
            location_id="loc-1",
            occupation="resident",
            workplace_id=None,
            status={},
        )
        world.agents["bob"] = AgentState(
            id="bob",
            name="Bob",
            location_id="loc-1",
            occupation="friend",
            workplace_id=None,
            status={},
        )
        world.agents["aaron"] = AgentState(
            id="aaron",
            name="Aaron",
            location_id="loc-1",
            occupation="mentor",
            workplace_id=None,
            status={},
        )

        snapshot = AgentDecisionSnapshot(
            id="alice",
            current_goal="talk",
            current_location_id="loc-1",
            home_location_id="loc-1",
            profile={"agent_config_id": "agent-partner"},
            recent_events=[
                {
                    "event_type": "speech",
                    "tick_no": 7,
                    "actor_agent_id": "bob",
                    "actor_name": "Bob",
                    "target_agent_id": "alice",
                    "target_name": "Alice",
                    "message": "我们继续刚才那份大纲吧。",
                    "payload": {
                        "conversation_id": "conv-1",
                        "participant_ids": ["alice", "bob", "aaron"],
                        "speaker_agent_id": "bob",
                    },
                }
            ],
        )

        intents, _ = await orchestrator.prepare_intents_from_data(
            world=world,
            agent_data=[snapshot],
            engine=None,
            run_id="run-partner-resolution",
            tick_no=8,
        )

        assert len(intents) == 1
        assert provider.captured_invocations[0].context["world"]["nearby_agent_id"] == "bob"
    finally:
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
    try:
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
    finally:
        shutil.rmtree(tmp_path)


@pytest.mark.asyncio
async def test_tick_orchestrator_uses_default_bundle_semantics_when_scenario_id_missing():
    tmp_path = Path(tempfile.mkdtemp())
    monkeypatch = pytest.MonkeyPatch()
    try:
        bundle_root = tmp_path / "scenarios" / "hero_world"
        agent_dir = bundle_root / "agents" / "hero"
        agent_dir.mkdir(parents=True)
        (bundle_root / "scenario.yml").write_text(
            "\n".join(
                [
                    "id: hero_world",
                    "name: Hero World",
                    "version: 1",
                    "adapter: bundle_world",
                    "default: true",
                    "semantics:",
                    "  subject_role: protagonist",
                    "  support_roles:",
                    "    - ally",
                    "  alert_metric: anomaly_score",
                ]
            ),
            encoding="utf-8",
        )
        (agent_dir / "agent.yml").write_text(
            "id: hero\nname: Hero\noccupation: resident\nhome: home\n",
            encoding="utf-8",
        )
        (agent_dir / "prompt.md").write_text("# Hero\nBase prompt", encoding="utf-8")

        monkeypatch.setenv("TRUMANWORLD_PROJECT_ROOT", str(tmp_path))
        get_settings.cache_clear()

        provider = TokenCapturingDecisionProvider()
        runtime = AgentRuntime(
            registry=AgentRegistry(bundle_root / "agents"),
            backend=HeuristicAgentBackend(provider),
        )
        orchestrator = TickOrchestrator(agent_runtime=runtime, scenario=FakeScenario())

        world = WorldState(current_time=datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc))
        world.agents["hero-1"] = type(
            "S", (), {"id": "hero-1", "status": {"anomaly_score": 0.55}, "location_id": "home"}
        )()
        snapshot = AgentDecisionSnapshot(
            id="hero-1",
            current_goal="rest",
            current_location_id="home",
            home_location_id="home",
            profile={"world_role": "protagonist", "agent_config_id": "hero"},
            recent_events=[],
        )

        intents, _ = await orchestrator.prepare_intents_from_data(
            world=world,
            agent_data=[snapshot],
            engine=None,
            run_id="run-default-semantics",
            tick_no=1,
        )

        assert len(intents) == 1
        assert provider.captured_invocations[0].context["world"]["subject_alert_score"] == 0.55
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()
        shutil.rmtree(tmp_path)


@pytest.mark.asyncio
async def test_prepare_intents_from_data_respects_runtime_concurrency_limit(db_session):
    run_id = "run-concurrency-limit-1"
    run = make_run(run_id, name="concurrency-limit", current_tick=1)
    agents = [
        make_agent(
            f"agent-limit-{i}",
            run_id=run_id,
            name=f"Agent {i}",
        )
        for i in range(3)
    ]
    db_session.add(run)
    db_session.add_all(agents)
    await db_session.commit()

    tmp_path = Path(tempfile.mkdtemp())
    try:
        for agent in agents:
            write_agent_config(tmp_path, agent.id, name=agent.name, home="loc-1")

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
    run = make_run(run_id, name="fallback-per-agent", current_tick=1)
    agents = [
        make_agent(
            "agent-fallback-ok",
            run_id=run_id,
            name="Agent OK",
        ),
        make_agent(
            "agent-fallback-bad",
            run_id=run_id,
            name="Agent Bad",
        ),
    ]
    db_session.add(run)
    db_session.add_all(agents)
    await db_session.commit()

    tmp_path = Path(tempfile.mkdtemp())
    try:
        for agent in agents:
            write_agent_config(tmp_path, agent.id, name=agent.name, home="loc-1")

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
        run = make_run(run_id, name="llm-persist")
        loc = make_location("loc-llm-1", run_id=run_id, name="Home", location_type="home")
        agent = make_agent(
            "agent-llm-p1",
            run_id=run_id,
            name="Alice",
            profile={"agent_config_id": agent_config_id},
            location_id="loc-llm-1",
        )
        session.add_all([run, loc, agent])
        await session.commit()

    tmp_path = Path(tempfile.mkdtemp())
    write_agent_config(tmp_path, agent_config_id, name="Alice", home="loc-llm-1")

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
        run = make_run(
            run_id,
            name="isolated-fallback",
            scenario_type="narrative_world",
        )
        home = make_location("loc-home-fb", run_id=run_id, name="Home", location_type="home")
        office = make_location(
            "loc-office-fb",
            run_id=run_id,
            name="Office",
            location_type="office",
        )
        ok_agent = make_agent(
            "agent-fallback-ok-iso",
            run_id=run_id,
            name="Alice",
            personality={},
            profile={"agent_config_id": "agent-fallback-ok-iso", "world_role": "cast"},
            status={},
            current_plan={},
        )
        ok_agent.home_location_id = home.id
        ok_agent.current_location_id = office.id
        bad_agent = make_agent(
            "agent-fallback-bad-iso",
            run_id=run_id,
            name="Bob",
            profile={"agent_config_id": "agent-fallback-bad-iso", "world_role": "cast"},
        )
        bad_agent.home_location_id = home.id
        bad_agent.current_location_id = office.id
        session.add_all([run, home, office, ok_agent, bad_agent])
        await session.commit()

    tmp_path = Path(tempfile.mkdtemp())
    try:
        for agent_id, name in (
            ("agent-fallback-ok-iso", "Alice"),
            ("agent-fallback-bad-iso", "Bob"),
        ):
            write_agent_config(tmp_path, agent_id, name=name, home="loc-home-fb")

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


@pytest.mark.asyncio
async def test_run_tick_isolated_reuses_conversation_id_across_adjacent_ticks():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    run_id = "run-isolated-conversation-continuity"
    async with AsyncSession(engine, expire_on_commit=False) as session:
        run = make_run(
            run_id,
            name="isolated-conversation-continuity",
        )
        cafe = make_location(
            "loc-cafe-iso-continuity",
            run_id=run_id,
            name="Cafe",
            location_type="cafe",
        )
        alice = make_agent(
            "alice-iso-continuity",
            run_id=run_id,
            location_id=cafe.id,
            name="Alice",
        )
        bob = make_agent(
            "bob-iso-continuity",
            run_id=run_id,
            location_id=cafe.id,
            name="Bob",
        )
        session.add_all([run, cafe, alice, bob])
        await session.commit()

    service = SimulationService.create_for_scheduler(
        AgentRuntime(
            registry=AgentRegistry(Path(tempfile.mkdtemp())), backend=HeuristicAgentBackend()
        )
    )

    try:
        await service.run_tick_isolated(
            run_id,
            engine,
            [
                ActionIntent(
                    agent_id="alice-iso-continuity",
                    action_type="talk",
                    target_agent_id="bob-iso-continuity",
                    payload={"message": "First tick"},
                )
            ],
        )
        await service.run_tick_isolated(
            run_id,
            engine,
            [
                ActionIntent(
                    agent_id="bob-iso-continuity",
                    action_type="talk",
                    target_agent_id="alice-iso-continuity",
                    payload={"message": "Second tick"},
                )
            ],
        )

        async with AsyncSession(engine, expire_on_commit=False) as session:
            timeline_events, _total = await EventRepository(session).list_timeline_events(
                run_id,
                order_desc=False,
            )
            conversation_started = [
                event for event in timeline_events if event.event_type == "conversation_started"
            ]
            speeches = [event for event in timeline_events if event.event_type == "speech"]

            assert len(conversation_started) == 1
            assert len(speeches) == 2
            conversation_id = conversation_started[0].payload["conversation_id"]
            assert speeches[0].payload["conversation_id"] == conversation_id
            assert speeches[1].payload["conversation_id"] == conversation_id
    finally:
        await engine.dispose()
