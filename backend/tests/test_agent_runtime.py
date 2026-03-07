import asyncio
from pathlib import Path

import pytest

import app.agent.providers as provider_module
from app.agent.context_builder import ContextBuilder
from app.agent.providers import AgentDecisionProvider, ClaudeSDKDecisionProvider, RuntimeDecision
from app.agent.planner import Planner
from app.agent.reactor import Reactor
from app.agent.reflector import Reflector
from app.agent.registry import AgentRegistry
from app.agent.runtime import AgentRuntime, RuntimeInvocation
from app.infra.settings import get_settings


@pytest.fixture
def runtime(tmp_path: Path) -> AgentRuntime:
    agent_dir = tmp_path / "demo_agent"
    agent_dir.mkdir(parents=True)
    (agent_dir / "agent.yml").write_text(
        "\n".join(
            [
                "id: demo_agent",
                "name: Demo Agent",
                "occupation: resident",
                "home: demo_home",
                "personality:",
                "  openness: 0.5",
                "capabilities:",
                "  dialogue: true",
                "  reflection: true",
                "model:",
                "  max_turns: 8",
                "  max_budget_usd: 1.0",
            ]
        ),
        encoding="utf-8",
    )
    (agent_dir / "prompt.md").write_text("# Demo Agent\nBase prompt", encoding="utf-8")

    registry = AgentRegistry(tmp_path)
    return AgentRuntime(registry=registry, context_builder=ContextBuilder())


class StubDecisionProvider(AgentDecisionProvider):
    async def decide(self, invocation):
        return RuntimeDecision(
            action_type="talk",
            target_agent_id="bob",
            payload={"intent_source": invocation.task},
        )


def test_runtime_prepare_planner(runtime: AgentRuntime):
    invocation = runtime.prepare_planner(
        "demo_agent",
        world={"time": "08:00", "location": "cafe"},
        memory={"recent": ["Met Bob yesterday"]},
    )

    assert invocation.agent_id == "demo_agent"
    assert invocation.task == "planner"
    assert invocation.context["task"] == "planner"
    assert invocation.context["world"]["location"] == "cafe"
    assert "运行上下文" in invocation.prompt
    assert '"location": "cafe"' in invocation.prompt


def test_runtime_prepare_reactor(runtime: AgentRuntime):
    invocation = runtime.prepare_reactor(
        "demo_agent",
        event={"type": "talk", "target": "bob"},
    )

    assert invocation.task == "reactor"
    assert invocation.context["event"]["target"] == "bob"
    assert invocation.allowed_actions == ["move", "talk", "work", "rest"]
    assert "只能返回一个 JSON 对象" in invocation.prompt
    assert '"task": "reactor"' in invocation.prompt


def test_runtime_prepare_reflector(runtime: AgentRuntime):
    invocation = runtime.prepare_reflector(
        "demo_agent",
        daily_summary={"highlights": ["Worked at cafe"]},
    )

    assert invocation.task == "reflector"
    assert invocation.context["daily_summary"]["highlights"] == ["Worked at cafe"]


def test_runtime_raises_for_unknown_agent(runtime: AgentRuntime):
    with pytest.raises(ValueError, match="Agent config not found"):
        runtime.prepare_planner("missing-agent")


def test_runtime_derive_intent_from_goal(runtime: AgentRuntime):
    invocation = runtime.prepare_reactor(
        "demo_agent",
        world={"current_goal": "move:park", "current_location_id": "home", "home_location_id": "home"},
    )

    intent = runtime.derive_intent(invocation)

    assert intent.action_type == "move"
    assert intent.target_location_id == "park"


def test_planner_reactor_reflector_wrap_runtime(runtime: AgentRuntime):
    planner = Planner(runtime)
    reactor = Reactor(runtime)
    reflector = Reflector(runtime)

    planner_call = planner.prepare("demo_agent")
    reactor_call = reactor.prepare("demo_agent", event={"type": "broadcast"})
    reflector_call = reflector.prepare("demo_agent", daily_summary={"done": True})

    assert planner_call.task == "planner"
    assert reactor_call.task == "reactor"
    assert reflector_call.task == "reflector"


@pytest.mark.asyncio
async def test_runtime_decide_intent_uses_provider(tmp_path: Path):
    agent_dir = tmp_path / "demo_agent"
    agent_dir.mkdir(parents=True)
    (agent_dir / "agent.yml").write_text(
        "\n".join(
            [
                "id: demo_agent",
                "name: Demo Agent",
                "occupation: resident",
                "home: demo_home",
            ]
        ),
        encoding="utf-8",
    )
    (agent_dir / "prompt.md").write_text("# Demo Agent\nBase prompt", encoding="utf-8")

    runtime = AgentRuntime(
        registry=AgentRegistry(tmp_path),
        context_builder=ContextBuilder(),
        decision_provider=StubDecisionProvider(),
    )

    invocation = runtime.prepare_reactor("demo_agent", world={"current_goal": "talk"})
    intent = await runtime.decide_intent(invocation)

    assert intent.action_type == "talk"
    assert intent.target_agent_id == "bob"
    assert intent.payload["intent_source"] == "reactor"


def test_runtime_selects_claude_provider_from_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TRUMANWORLD_AGENT_PROVIDER", "claude")
    get_settings.cache_clear()

    agent_dir = tmp_path / "demo_agent"
    agent_dir.mkdir(parents=True)
    (agent_dir / "agent.yml").write_text(
        "\n".join(
            [
                "id: demo_agent",
                "name: Demo Agent",
                "occupation: resident",
                "home: demo_home",
            ]
        ),
        encoding="utf-8",
    )
    (agent_dir / "prompt.md").write_text("# Demo Agent\nBase prompt", encoding="utf-8")

    runtime = AgentRuntime(
        registry=AgentRegistry(tmp_path),
        context_builder=ContextBuilder(),
    )

    assert isinstance(runtime.decision_provider, ClaudeSDKDecisionProvider)

    get_settings.cache_clear()


def test_runtime_selects_claude_provider_from_legacy_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TRUMANWORLD_AGENT_PROVIDER", "anthropic")
    monkeypatch.setenv("TRUMANWORLD_ANTHROPIC_MODEL", "legacy-model")
    get_settings.cache_clear()

    agent_dir = tmp_path / "demo_agent"
    agent_dir.mkdir(parents=True)
    (agent_dir / "agent.yml").write_text(
        "\n".join(
            [
                "id: demo_agent",
                "name: Demo Agent",
                "occupation: resident",
                "home: demo_home",
            ]
        ),
        encoding="utf-8",
    )
    (agent_dir / "prompt.md").write_text("# Demo Agent\nBase prompt", encoding="utf-8")

    runtime = AgentRuntime(
        registry=AgentRegistry(tmp_path),
        context_builder=ContextBuilder(),
    )

    settings = get_settings()
    assert settings.agent_provider == "claude"
    assert settings.agent_model == "legacy-model"
    assert isinstance(runtime.decision_provider, ClaudeSDKDecisionProvider)

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_claude_provider_wraps_cancelled_error(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TRUMANWORLD_AGENT_PROVIDER", "claude")
    get_settings.cache_clear()
    monkeypatch.setattr(provider_module.shutil, "which", lambda _: "/usr/bin/claude")

    async def fake_query(*args, **kwargs):
        raise asyncio.CancelledError
        yield  # pragma: no cover

    monkeypatch.setattr(provider_module, "query", fake_query)

    provider = ClaudeSDKDecisionProvider(get_settings())
    invocation = RuntimeInvocation(
        agent_id="alice",
        task="reactor",
        prompt="test",
        context={},
        max_turns=1,
        max_budget_usd=0.1,
    )

    with pytest.raises(RuntimeError, match="decision cancelled"):
        await provider.decide(invocation)

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_claude_provider_fails_fast_when_cli_missing(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TRUMANWORLD_AGENT_PROVIDER", "claude")
    monkeypatch.setattr(provider_module.shutil, "which", lambda _: None)
    get_settings.cache_clear()

    provider = ClaudeSDKDecisionProvider(get_settings())
    invocation = RuntimeInvocation(
        agent_id="alice",
        task="reactor",
        prompt="test",
        context={},
        max_turns=1,
        max_budget_usd=0.1,
    )

    with pytest.raises(RuntimeError, match="Claude CLI is not available"):
        await provider.decide(invocation)

    get_settings.cache_clear()
