from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
import shutil
import tempfile

import pytest

from app.agent.runtime import RuntimeInvocation
from app.cognition.claude.decision_provider import AgentDecisionProvider
from app.cognition.claude.decision_utils import RuntimeDecision
from app.cognition.errors import UpstreamApiUnavailableError
from app.cognition.heuristic.agent_backend import HeuristicAgentBackend
from app.infra.settings import get_settings
from app.scenario.types import ScenarioGuidance
from app.sim.action_resolver import ActionIntent
from app.sim.types import AgentDecisionSnapshot
from app.sim.world import AgentState, LocationState, WorldState
from tests.factories import make_agent, make_run, write_agent_config

from .helpers import build_orchestrator
from .test_service import FakeScenario, MixedOutcomeDecisionProvider
from .test_service_isolated import FixedTalkDecisionProvider, TokenCapturingDecisionProvider


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
    orchestrator = build_orchestrator(tmp_path, provider=provider, scenario=FakeScenario())

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
        orchestrator = build_orchestrator(tmp_path, provider=provider, scenario=FakeScenario())

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
        orchestrator = build_orchestrator(tmp_path, provider=provider, scenario=FakeScenario())

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
        orchestrator = build_orchestrator(tmp_path, provider=provider, scenario=FakeScenario())

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
        orchestrator = build_orchestrator(tmp_path, provider=provider, scenario=FakeScenario())

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
        orchestrator = build_orchestrator(tmp_path, provider=provider, scenario=FakeScenario())

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
        orchestrator = build_orchestrator(
            tmp_path, backend=UnavailableApiBackend(), scenario=FakeScenario()
        )
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
        orchestrator = build_orchestrator(
            bundle_root / "agents", provider=provider, scenario=FakeScenario()
        )

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
        orchestrator = build_orchestrator(
            tmp_path, backend=LimitedBackend(provider), scenario=FakeScenario()
        )

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

        orchestrator = build_orchestrator(
            tmp_path, provider=provider, scenario=FallbackScenario()
        )

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


