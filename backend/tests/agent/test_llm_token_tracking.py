"""Tests for LLM token statistics completeness.

This test verifies that all LLM call paths properly record token usage:
1. reactor (decision) - already working
2. planner (morning planning) - missing
3. reflector (evening reflection) - missing
4. director - missing (out of scope for this fix)
"""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
import asyncio
import os

from claude_agent_sdk import ResultMessage
from app.agent.runtime import AgentRuntime, RuntimeContext
from app.agent.registry import AgentRegistry
from app.agent.providers import AgentDecisionProvider, RuntimeDecision


class TokenCapturingProvider(AgentDecisionProvider):
    """A provider that captures runtime_ctx and triggers on_llm_call callback."""

    def __init__(self):
        self.captured_ctx = []

    async def decide(self, invocation, runtime_ctx=None):
        self.captured_ctx.append(runtime_ctx)
        # Simulate triggering the callback (like real SDK would)
        if runtime_ctx and runtime_ctx.on_llm_call:
            runtime_ctx.on_llm_call(
                agent_id=invocation.agent_id,
                task_type=invocation.task,
                usage={"input_tokens": 100, "output_tokens": 200},
                total_cost_usd=0.01,
                duration_ms=500,
            )
        return RuntimeDecision(action_type="rest")


@pytest.fixture
def agent_runtime_with_mock_provider(tmp_path: Path):
    """Create an AgentRuntime with mock provider for testing."""
    agent_dir = tmp_path / "test_agent"
    agent_dir.mkdir(parents=True)
    (agent_dir / "agent.yml").write_text(
        "id: test_agent\nname: Test Agent\noccupation: resident\nhome: home\n",
        encoding="utf-8",
    )
    (agent_dir / "prompt.md").write_text("# Test Agent\nBase prompt", encoding="utf-8")

    registry = AgentRegistry(tmp_path)
    provider = TokenCapturingProvider()
    runtime = AgentRuntime(registry=registry, decision_provider=provider)
    return runtime, provider


@pytest.fixture
def agent_runtime_claude_provider(tmp_path: Path):
    """Create an AgentRuntime with Claude provider for testing LLM calls."""
    # Set up environment for Claude provider
    original_env = os.environ.get("TRUMANWORLD_AGENT_PROVIDER")
    os.environ["TRUMANWORLD_AGENT_PROVIDER"] = "claude"

    # Clear settings cache
    from app.infra.settings import get_settings

    get_settings.cache_clear()

    agent_dir = tmp_path / "test_agent"
    agent_dir.mkdir(parents=True)
    (agent_dir / "agent.yml").write_text(
        "id: test_agent\nname: Test Agent\noccupation: resident\nhome: home\n",
        encoding="utf-8",
    )
    (agent_dir / "prompt.md").write_text("# Test Agent\nBase prompt", encoding="utf-8")

    registry = AgentRegistry(tmp_path)
    runtime = AgentRuntime(registry=registry)

    yield runtime, tmp_path

    # Restore environment
    if original_env is None:
        os.environ.pop("TRUMANWORLD_AGENT_PROVIDER", None)
    else:
        os.environ["TRUMANWORLD_AGENT_PROVIDER"] = original_env
    get_settings.cache_clear()


class TestReactorTokenTracking:
    """Test that reactor (decision) LLM calls properly record tokens."""

    @pytest.mark.asyncio
    async def test_reactor_llm_call_triggers_callback(self, agent_runtime_with_mock_provider):
        """Verify that reactor decision triggers on_llm_call callback."""
        runtime, provider = agent_runtime_with_mock_provider

        # Create runtime context with callback
        captured_records = []

        def on_llm_call(agent_id, task_type, usage, total_cost_usd, duration_ms):
            captured_records.append(
                {
                    "agent_id": agent_id,
                    "task_type": task_type,
                    "usage": usage,
                    "cost": total_cost_usd,
                    "duration": duration_ms,
                }
            )

        runtime_ctx = RuntimeContext(on_llm_call=on_llm_call)

        # Call react (which internally calls decide)
        await runtime.react(
            agent_id="test_agent",
            world={
                "current_goal": "rest",
                "current_location_id": "home",
                "home_location_id": "home",
            },
            runtime_ctx=runtime_ctx,
        )

        # Verify callback was triggered
        assert len(captured_records) == 1
        assert captured_records[0]["task_type"] == "reactor"
        assert captured_records[0]["usage"]["input_tokens"] == 100
        print(f"✓ Reactor token tracking works: {captured_records}")


class TestPlannerTokenTracking:
    """Test that planner (morning planning) LLM calls properly record tokens."""

    @pytest.mark.asyncio
    async def test_run_planner_llm_call_triggers_callback(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Verify that run_planner triggers on_llm_call callback."""
        # Import and mock settings before anything else
        import app.agent.runtime as runtime_module
        from app.infra.settings import Settings

        # Create mock settings
        mock_settings = MagicMock(spec=Settings)
        mock_settings.agent_provider = "claude"
        mock_settings.agent_model = "claude-sonnet-4-20250514"
        mock_settings.anthropic_api_key = "test-key"
        mock_settings.anthropic_base_url = None
        mock_settings.project_root = tmp_path

        # Monkey patch get_settings in the runtime module
        monkeypatch.setattr(runtime_module, "get_settings", lambda: mock_settings)
        # Also patch shutil.which
        monkeypatch.setattr(
            runtime_module.shutil, "which", lambda x: "/usr/bin/claude" if x == "claude" else None
        )

        agent_dir = tmp_path / "test_agent"
        agent_dir.mkdir(parents=True)
        (agent_dir / "agent.yml").write_text(
            "id: test_agent\nname: Test Agent\noccupation: resident\nhome: home\n",
            encoding="utf-8",
        )
        (agent_dir / "prompt.md").write_text("# Test Agent\nBase prompt", encoding="utf-8")

        registry = AgentRegistry(tmp_path)
        runtime = AgentRuntime(registry=registry)

        # Create runtime context with callback
        captured_records = []

        def on_llm_call(agent_id, task_type, usage, total_cost_usd, duration_ms):
            captured_records.append(
                {
                    "agent_id": agent_id,
                    "task_type": task_type,
                    "usage": usage,
                    "cost": total_cost_usd,
                    "duration": duration_ms,
                }
            )

        runtime_ctx = RuntimeContext(on_llm_call=on_llm_call)

        # Mock the claude_agent_sdk.query
        mock_result = asyncio.Queue()
        await mock_result.put(
            MagicMock(
                spec=ResultMessage,
                is_error=False,
                usage={"input_tokens": 150, "output_tokens": 300},
                total_cost_usd=0.02,
                duration_ms=1000,
                result='{"morning": "work", "daytime": "work", "evening": "rest"}',
            )
        )

        async def mock_query(*args, **kwargs):
            while not mock_result.empty():
                yield await mock_result.get()

        with patch("claude_agent_sdk.query", mock_query):
            # Call run_planner with runtime_ctx
            await runtime.run_planner(
                agent_id="test_agent",
                agent_name="Test Agent",
                world_context={"time": "08:00"},
                runtime_ctx=runtime_ctx,  # Pass runtime_ctx
            )

        # Verify callback was triggered
        assert len(captured_records) == 1, (
            f"Expected 1 token record for planner, got {len(captured_records)}. "
            "This indicates run_planner does not trigger on_llm_call callback."
        )
        assert captured_records[0]["task_type"] == "planner"
        assert captured_records[0]["usage"]["input_tokens"] == 150
        print(f"✓ Planner token tracking works: {captured_records}")


class TestReflectorTokenTracking:
    """Test that reflector (evening reflection) LLM calls properly record tokens."""

    @pytest.mark.asyncio
    async def test_run_reflector_llm_call_triggers_callback(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Verify that run_reflector triggers on_llm_call callback."""
        # Import and mock settings before anything else
        import app.agent.runtime as runtime_module
        from app.infra.settings import Settings

        # Create mock settings
        mock_settings = MagicMock(spec=Settings)
        mock_settings.agent_provider = "claude"
        mock_settings.agent_model = "claude-sonnet-4-20250514"
        mock_settings.anthropic_api_key = "test-key"
        mock_settings.anthropic_base_url = None
        mock_settings.project_root = tmp_path

        # Monkey patch get_settings in the runtime module
        monkeypatch.setattr(runtime_module, "get_settings", lambda: mock_settings)
        # Also patch shutil.which
        monkeypatch.setattr(
            runtime_module.shutil, "which", lambda x: "/usr/bin/claude" if x == "claude" else None
        )

        agent_dir = tmp_path / "test_agent"
        agent_dir.mkdir(parents=True)
        (agent_dir / "agent.yml").write_text(
            "id: test_agent\nname: Test Agent\noccupation: resident\nhome: home\n",
            encoding="utf-8",
        )
        (agent_dir / "prompt.md").write_text("# Test Agent\nBase prompt", encoding="utf-8")

        registry = AgentRegistry(tmp_path)
        runtime = AgentRuntime(registry=registry)

        # Create runtime context with callback
        captured_records = []

        def on_llm_call(agent_id, task_type, usage, total_cost_usd, duration_ms):
            captured_records.append(
                {
                    "agent_id": agent_id,
                    "task_type": task_type,
                    "usage": usage,
                    "cost": total_cost_usd,
                    "duration": duration_ms,
                }
            )

        runtime_ctx = RuntimeContext(on_llm_call=on_llm_call)

        # Mock the claude_agent_sdk.query
        mock_result = asyncio.Queue()
        await mock_result.put(
            MagicMock(
                spec=ResultMessage,
                is_error=False,
                usage={"input_tokens": 200, "output_tokens": 400},
                total_cost_usd=0.03,
                duration_ms=1500,
                result='{"reflection": "Good day", "mood": "happy"}',
            )
        )

        async def mock_query(*args, **kwargs):
            while not mock_result.empty():
                yield await mock_result.get()

        with patch("claude_agent_sdk.query", mock_query):
            # Call run_reflector with runtime_ctx
            await runtime.run_reflector(
                agent_id="test_agent",
                agent_name="Test Agent",
                world_context={"time": "20:00"},
                runtime_ctx=runtime_ctx,  # Pass runtime_ctx
            )

        # Verify callback was triggered
        assert len(captured_records) == 1, (
            f"Expected 1 token record for reflector, got {len(captured_records)}. "
            "This indicates run_reflector does not trigger on_llm_call callback."
        )
        assert captured_records[0]["task_type"] == "reflector"
        assert captured_records[0]["usage"]["input_tokens"] == 200
        print(f"✓ Reflector token tracking works: {captured_records}")
