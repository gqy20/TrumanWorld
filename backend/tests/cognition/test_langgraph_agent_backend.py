from __future__ import annotations

from unittest.mock import patch

from app.cognition.registry import CognitionRegistry
from app.cognition.types import AgentActionInvocation, BackendExecutionContext
from app.infra.settings import Settings


def test_registry_builds_langgraph_agent_backend() -> None:
    settings = Settings(agent_backend="langgraph", director_backend="heuristic")

    backend = CognitionRegistry(settings).build_agent_backend()

    assert backend.__class__.__name__ == "LangGraphAgentBackend"


async def test_langgraph_backend_decides_move_for_direct_goal() -> None:
    from app.cognition.langgraph.agent_backend import LangGraphAgentBackend

    backend = LangGraphAgentBackend()
    invocation = AgentActionInvocation(
        agent_id="alice",
        prompt="Pick the next action.",
        context={
            "world": {
                "current_goal": "move:town-square",
                "known_location_ids": ["town-square", "home"],
            }
        },
        max_turns=2,
        max_budget_usd=0.1,
        allowed_actions=["move", "talk", "work", "rest"],
    )

    result = await backend.decide_action(invocation)

    assert result.action_type == "move"
    assert result.target_location_id == "town-square"


async def test_langgraph_backend_falls_back_to_rest_without_directive() -> None:
    from app.cognition.langgraph.agent_backend import LangGraphAgentBackend

    backend = LangGraphAgentBackend()
    invocation = AgentActionInvocation(
        agent_id="alice",
        prompt="Pick the next action.",
        context={"world": {"current_goal": "talk", "known_location_ids": ["town-square"]}},
        max_turns=2,
        max_budget_usd=0.1,
        allowed_actions=["move", "talk", "work", "rest"],
    )

    result = await backend.decide_action(invocation)

    assert result.action_type == "rest"


async def test_langgraph_backend_uses_structured_model_decision() -> None:
    from app.cognition.langgraph.agent_backend import LangGraphAgentBackend

    class FakeStructuredModel:
        def __init__(self) -> None:
            self.prompts: list[str] = []

        def with_structured_output(self, schema):
            return self

        async def ainvoke(self, prompt: str):
            self.prompts.append(prompt)
            return {
                "action_type": "talk",
                "target_agent_id": "bob",
                "message": "Morning, Bob.",
                "payload": {"source": "langgraph-model"},
            }

    model = FakeStructuredModel()
    backend = LangGraphAgentBackend(decision_model=model)
    invocation = AgentActionInvocation(
        agent_id="alice",
        prompt="Pick the next action.",
        context={"world": {"current_goal": "talk", "nearby_agent_id": "bob"}},
        max_turns=2,
        max_budget_usd=0.1,
        allowed_actions=["move", "talk", "work", "rest"],
    )

    result = await backend.decide_action(invocation)

    assert result.action_type == "talk"
    assert result.target_agent_id == "bob"
    assert result.message == "Morning, Bob."
    assert result.payload == {"source": "langgraph-model"}
    assert model.prompts
    assert "Pick the next action." in model.prompts[0]


async def test_langgraph_backend_falls_back_when_model_errors() -> None:
    from app.cognition.langgraph.agent_backend import LangGraphAgentBackend

    class FailingStructuredModel:
        def with_structured_output(self, schema):
            return self

        async def ainvoke(self, prompt: str):
            raise RuntimeError("model unavailable")

    backend = LangGraphAgentBackend(decision_model=FailingStructuredModel())
    invocation = AgentActionInvocation(
        agent_id="alice",
        prompt="Pick the next action.",
        context={
            "world": {
                "current_goal": "move:town-square",
                "known_location_ids": ["town-square", "home"],
            }
        },
        max_turns=2,
        max_budget_usd=0.1,
        allowed_actions=["move", "talk", "work", "rest"],
    )

    result = await backend.decide_action(invocation)

    assert result.action_type == "move"
    assert result.target_location_id == "town-square"


async def test_langgraph_backend_retries_transient_model_failures() -> None:
    from app.cognition.langgraph.agent_backend import LangGraphAgentBackend

    class FlakyStructuredModel:
        def __init__(self) -> None:
            self.calls = 0

        def with_structured_output(self, schema):
            return self

        async def ainvoke(self, prompt: str):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("temporary model failure")
            return {
                "action_type": "talk",
                "target_agent_id": "bob",
                "message": "Retry succeeded.",
            }

    model = FlakyStructuredModel()
    backend = LangGraphAgentBackend(decision_model=model)
    invocation = AgentActionInvocation(
        agent_id="alice",
        prompt="Pick the next action.",
        context={"world": {"current_goal": "talk", "nearby_agent_id": "bob"}},
        max_turns=2,
        max_budget_usd=0.1,
        allowed_actions=["move", "talk", "work", "rest"],
    )

    result = await backend.decide_action(invocation)

    assert model.calls == 2
    assert result.action_type == "talk"
    assert result.target_agent_id == "bob"
    assert result.message == "Retry succeeded."


async def test_langgraph_backend_rejects_invalid_talk_without_message() -> None:
    from app.cognition.langgraph.agent_backend import LangGraphAgentBackend

    class InvalidTalkModel:
        def with_structured_output(self, schema):
            return self

        async def ainvoke(self, prompt: str):
            return {
                "action_type": "talk",
                "target_agent_id": "bob",
            }

    backend = LangGraphAgentBackend(decision_model=InvalidTalkModel())
    invocation = AgentActionInvocation(
        agent_id="alice",
        prompt="Pick the next action.",
        context={"world": {"current_goal": "talk", "nearby_agent_id": "bob"}},
        max_turns=2,
        max_budget_usd=0.1,
        allowed_actions=["move", "talk", "work", "rest"],
    )

    result = await backend.decide_action(invocation)

    assert result.action_type == "rest"


async def test_langgraph_backend_rejects_invalid_move_without_target() -> None:
    from app.cognition.langgraph.agent_backend import LangGraphAgentBackend

    class InvalidMoveModel:
        def with_structured_output(self, schema):
            return self

        async def ainvoke(self, prompt: str):
            return {
                "action_type": "move",
            }

    backend = LangGraphAgentBackend(decision_model=InvalidMoveModel())
    invocation = AgentActionInvocation(
        agent_id="alice",
        prompt="Pick the next action.",
        context={
            "world": {
                "current_goal": "move:town-square",
                "known_location_ids": ["town-square", "home"],
            }
        },
        max_turns=2,
        max_budget_usd=0.1,
        allowed_actions=["move", "talk", "work", "rest"],
    )

    result = await backend.decide_action(invocation)

    assert result.action_type == "move"
    assert result.target_location_id == "town-square"


async def test_langgraph_backend_reports_usage_via_runtime_context() -> None:
    import asyncio

    from app.cognition.langgraph.agent_backend import LangGraphAgentBackend

    class FakeStructuredResponse(dict):
        def __init__(self) -> None:
            super().__init__(
                action_type="rest",
                payload={"source": "langgraph-model"},
            )
            self.usage_metadata = {"input_tokens": 11, "output_tokens": 7}

    class FakeStructuredModel:
        def with_structured_output(self, schema):
            return self

        async def ainvoke(self, prompt: str):
            await asyncio.sleep(0.01)
            return FakeStructuredResponse()

    recorded: list[dict] = []

    def on_llm_call(agent_id, task_type, usage, total_cost_usd, duration_ms):
        recorded.append(
            {
                "agent_id": agent_id,
                "task_type": task_type,
                "usage": usage,
                "cost": total_cost_usd,
                "duration": duration_ms,
            }
        )

    backend = LangGraphAgentBackend(decision_model=FakeStructuredModel())
    invocation = AgentActionInvocation(
        agent_id="alice",
        prompt="Pick the next action.",
        context={"world": {"current_goal": "rest"}},
        max_turns=2,
        max_budget_usd=0.1,
        allowed_actions=["move", "talk", "work", "rest"],
    )
    runtime_ctx = BackendExecutionContext(on_llm_call=on_llm_call)

    result = await backend.decide_action(invocation, runtime_ctx=runtime_ctx)

    assert result.action_type == "rest"
    assert len(recorded) == 1
    assert recorded[0]["agent_id"] == "alice"
    assert recorded[0]["task_type"] == "reactor"
    assert recorded[0]["usage"] == {"input_tokens": 11, "output_tokens": 7}
    assert recorded[0]["cost"] == 0.0
    assert recorded[0]["duration"] > 0


def test_langgraph_backend_builds_default_model_from_langgraph_settings() -> None:
    from app.cognition.langgraph.agent_backend import LangGraphAgentBackend

    settings = Settings(
        agent_backend="langgraph",
        langgraph_model="claude-sonnet-test",
        langgraph_api_key="langgraph-key",
        langgraph_base_url="https://proxy.invalid/anthropic",
    )
    captured: dict = {}

    class FakeChatAnthropic:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

    with patch("langchain_anthropic.ChatAnthropic", FakeChatAnthropic):
        backend = LangGraphAgentBackend(settings=settings)

    assert backend._decision_model is not None
    assert captured["model"] == "claude-sonnet-test"
    assert captured["api_key"] == "langgraph-key"
    assert captured["base_url"] == "https://proxy.invalid/anthropic"
    assert captured["temperature"] == 0


def test_langgraph_backend_builds_default_model_from_shared_env_fields() -> None:
    from app.cognition.langgraph.agent_backend import LangGraphAgentBackend

    settings = Settings(
        agent_backend="langgraph",
        agent_model="shared-agent-model",
        anthropic_api_key="shared-anthropic-key",
        anthropic_base_url="https://shared.invalid/anthropic",
    )
    captured: dict = {}

    class FakeChatAnthropic:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

    with patch("langchain_anthropic.ChatAnthropic", FakeChatAnthropic):
        backend = LangGraphAgentBackend(settings=settings)

    assert backend._decision_model is not None
    assert captured["model"] == "shared-agent-model"
    assert captured["api_key"] == "shared-anthropic-key"
    assert captured["base_url"] == "https://shared.invalid/anthropic"
