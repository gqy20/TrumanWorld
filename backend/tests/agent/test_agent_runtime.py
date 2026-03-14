import asyncio
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.agent.context_builder import ContextBuilder
from app.agent.planner import Planner
from app.agent.reactor import Reactor
from app.agent.reflector import Reflector
from app.agent.registry import AgentRegistry
from app.agent.runtime import AgentRuntime, RuntimeInvocation
from app.cognition.claude.agent_backend import ClaudeSdkAgentBackend
from app.cognition.types import AgentDecisionResult
from app.agent.system_prompt import build_system_prompt
import app.cognition.claude.decision_provider as provider_module
from app.cognition.claude.decision_provider import ClaudeSDKDecisionProvider
from app.infra.settings import get_settings
from app.scenario.truman_world.scenario import TrumanWorldScenario


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
    runtime = AgentRuntime(registry=registry, context_builder=ContextBuilder())
    TrumanWorldScenario().configure_runtime(runtime)
    return runtime


class StubDecisionBackend:
    async def decide_action(self, invocation, runtime_ctx=None):
        return AgentDecisionResult(
            action_type="talk",
            target_agent_id="bob",
            payload={"intent_source": "reactor"},
        )

    async def plan_day(self, invocation, runtime_ctx=None):
        return None

    async def reflect_day(self, invocation, runtime_ctx=None):
        return None


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
    assert invocation.context["role_context"]["perspective"] == "supporting_cast"
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
    assert invocation.context["role_context"]["perspective"] == "supporting_cast"
    assert "只能返回一个 JSON 对象" in invocation.prompt
    assert '"task": "reactor"' in invocation.prompt


def test_runtime_prepare_reactor_adds_truman_role_context(tmp_path: Path):
    agent_dir = tmp_path / "truman"
    agent_dir.mkdir(parents=True)
    (agent_dir / "agent.yml").write_text(
        "\n".join(
            [
                "id: truman",
                "name: Truman",
                "world_role: truman",
                "occupation: resident",
                "home: demo_home",
            ]
        ),
        encoding="utf-8",
    )
    (agent_dir / "prompt.md").write_text("# Truman\nBase prompt", encoding="utf-8")

    runtime = AgentRuntime(registry=AgentRegistry(tmp_path), context_builder=ContextBuilder())
    TrumanWorldScenario().configure_runtime(runtime)
    invocation = runtime.prepare_reactor(
        "truman",
        world={
            "current_goal": "rest",
            "self_status": {"suspicion_score": 0.25},
            "director_hint": "ignore-me",
        },
    )

    assert invocation.context["world_role"] == "truman"
    assert invocation.context["role_context"]["perspective"] == "subjective"
    assert invocation.context["role_context"]["current_suspicion_score"] == 0.25
    assert "director_hint" not in invocation.context["world"]


def test_runtime_prepare_reactor_adds_cast_scene_guidance(tmp_path: Path):
    agent_dir = tmp_path / "cast_agent"
    agent_dir.mkdir(parents=True)
    (agent_dir / "agent.yml").write_text(
        "\n".join(
            [
                "id: cast_agent",
                "name: Cast Agent",
                "world_role: cast",
                "occupation: resident",
                "home: demo_home",
            ]
        ),
        encoding="utf-8",
    )
    (agent_dir / "prompt.md").write_text("# Cast Agent\nBase prompt", encoding="utf-8")

    runtime = AgentRuntime(registry=AgentRegistry(tmp_path), context_builder=ContextBuilder())
    TrumanWorldScenario().configure_runtime(runtime)
    invocation = runtime.prepare_reactor(
        "cast_agent",
        world={
            "current_goal": "rest",
            "director_scene_goal": "soft_check_in",
            "director_priority": "advisory",
            "director_message_hint": "如果自然碰到 Truman，可以顺着熟悉话题聊几句",
            "director_target_agent_id": "truman",
            "director_reason": "Truman 怀疑度升高",
        },
    )

    assert invocation.context["scene_guidance"]["scene_goal"] == "soft_check_in"
    assert invocation.context["scene_guidance"]["priority"] == "advisory"
    assert invocation.context["scene_guidance"]["target_agent_id"] == "truman"
    assert invocation.context["scene_guidance"]["is_advisory"] is True


def test_decision_prompt_requires_message_field_for_talk(runtime: AgentRuntime):
    invocation = runtime.prepare_reactor(
        "demo_agent",
        world={"current_goal": "talk", "nearby_agent_id": "bob"},
    )

    assert (
        "JSON 仅可包含字段：`action_type`、`target_location_id`、`target_agent_id`、`message`、`payload`"
        in invocation.prompt
    )
    assert (
        "当 `action_type=talk` 时，必须提供 `target_agent_id` 与 `message`（30-200 字的自然发言；会在执行层映射为 speech 事件）"
        in invocation.prompt
    )


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
        backend=StubDecisionBackend(),
    )

    invocation = runtime.prepare_reactor("demo_agent", world={"current_goal": "talk"})
    intent = await runtime.decide_intent(invocation)

    assert intent.action_type == "talk"
    assert intent.target_agent_id == "bob"
    assert intent.payload["intent_source"] == "reactor"


@pytest.mark.asyncio
async def test_heuristic_provider_returns_rest_for_talk_goal(runtime: AgentRuntime):
    """HeuristicDecisionProvider no longer handles talk goal — delegates to LLM (rest fallback)."""
    invocation = runtime.prepare_reactor(
        "demo_agent",
        world={
            "current_goal": "talk",
            "current_location_id": "cafe",
            "home_location_id": "home",
            "nearby_agent_id": "bob",
        },
    )

    intent = await runtime.decide_intent(invocation)

    # Heuristic no longer handles talk — only move:xxx is handled; everything else falls back to rest
    assert intent.action_type == "rest"


@pytest.mark.asyncio
async def test_runtime_rest_when_work_goal_has_no_valid_work_context(runtime: AgentRuntime):
    invocation = runtime.prepare_reactor(
        "demo_agent",
        world={
            "current_goal": "work",
            "current_location_id": "home",
            "current_location_type": "home",
            "home_location_id": "home",
        },
    )

    intent = await runtime.decide_intent(invocation)

    assert intent.action_type == "rest"


def test_runtime_selects_claude_provider_from_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TRUMANWORLD_AGENT_BACKEND", "claude_sdk")
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

    assert isinstance(runtime.backend, ClaudeSdkAgentBackend)

    get_settings.cache_clear()


def test_runtime_selects_langgraph_backend_from_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("TRUMANWORLD_AGENT_BACKEND", "langgraph")
    monkeypatch.setenv("TRUMANWORLD_AGENT_MODEL", "claude-test")
    monkeypatch.setenv("TRUMANWORLD_ANTHROPIC_API_KEY", "test-key")
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

    assert runtime.backend.__class__.__name__ == "LangGraphAgentBackend"
    assert runtime.backend.__class__.__name__ == "LangGraphAgentBackend"

    get_settings.cache_clear()


def test_claude_provider_builds_options_with_system_prompt(tmp_path: Path):
    settings = get_settings()
    provider = ClaudeSDKDecisionProvider(settings)
    invocation = RuntimeInvocation(
        agent_id="demo_agent",
        task="reactor",
        prompt="Base prompt",
        context={},
        max_turns=2,
        max_budget_usd=0.2,
        allowed_actions=["move", "talk", "work", "rest"],
    )

    options = provider._build_sdk_options(invocation)

    assert options.system_prompt == build_system_prompt()


def test_runtime_rejects_legacy_anthropic_provider_value(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TRUMANWORLD_AGENT_BACKEND", "anthropic")
    get_settings.cache_clear()

    with pytest.raises(ValidationError):
        get_settings()

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_claude_provider_returns_fallback_on_cancelled_error(monkeypatch: pytest.MonkeyPatch):
    """Test that CancelledError returns a fallback decision instead of raising.

    This behavior allows the simulation to continue gracefully when
    the SDK call is cancelled (e.g., scheduler shutdown).
    """
    monkeypatch.setenv("TRUMANWORLD_AGENT_BACKEND", "claude_sdk")
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

    # CancelledError should return a fallback decision, not raise
    result = await provider.decide(invocation)
    assert result.action_type == "rest"

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_runtime_decide_intent_accepts_empty_message_when_llm_omits_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """When LLM omits message, decide_intent accepts the empty value without injecting a default."""
    monkeypatch.setenv("TRUMANWORLD_AGENT_BACKEND", "claude_sdk")
    get_settings.cache_clear()
    monkeypatch.setattr(provider_module.shutil, "which", lambda _: "/usr/bin/claude")

    async def fake_query(*args, **kwargs):
        yield provider_module.ResultMessage(
            subtype="result",
            duration_ms=1,
            duration_api_ms=1,
            is_error=False,
            num_turns=1,
            session_id="session-1",
            result='{"action_type":"talk","target_agent_id":"bob"}',
        )

    monkeypatch.setattr(provider_module, "query", fake_query)

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
        backend=ClaudeSdkAgentBackend(get_settings()),
    )

    invocation = runtime.prepare_reactor(
        "demo_agent",
        world={
            "current_goal": "talk",
            "current_location_id": "cafe",
            "home_location_id": "home",
            "nearby_agent_id": "bob",
        },
    )

    result = await runtime.decide_intent(invocation)

    assert result.action_type == "talk"
    assert result.target_agent_id == "bob"
    # LLM did not provide message — accepted as empty (no default injection)
    assert "message" not in result.payload

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_claude_provider_fails_fast_when_cli_missing(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TRUMANWORLD_AGENT_BACKEND", "claude_sdk")
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
