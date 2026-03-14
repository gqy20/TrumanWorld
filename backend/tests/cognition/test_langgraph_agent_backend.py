from __future__ import annotations

from unittest.mock import patch

import pytest

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

    backend = LangGraphAgentBackend(
        settings=Settings(
            agent_backend="langgraph",
            langgraph_model=None,
            langgraph_api_key=None,
            langgraph_base_url=None,
            agent_model=None,
            anthropic_api_key=None,
            anthropic_base_url=None,
        )
    )
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


async def test_langgraph_backend_prefers_text_json_by_default() -> None:
    from app.cognition.langgraph.agent_backend import LangGraphAgentBackend

    class FakeTextFirstModel:
        def __init__(self) -> None:
            self.prompts: list[object] = []
            self.structured_calls: list[dict] = []

        def with_structured_output(self, schema, *, method=None, include_raw=False):
            self.structured_calls.append(
                {"schema": schema, "method": method, "include_raw": include_raw}
            )
            return self

        async def ainvoke(self, prompt: str):
            self.prompts.append(prompt)
            return """
            {
              "action_type": "talk",
              "target_agent_id": "bob",
              "message": "Morning, Bob.",
              "payload": {"source": "langgraph-model"}
            }
            """

    model = FakeTextFirstModel()
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
    assert model.structured_calls == []
    first_prompt = model.prompts[0]
    assert isinstance(first_prompt, list)
    first_message = first_prompt[0]
    assert first_message.content[0]["cache_control"] == {"type": "ephemeral"}
    assert "Pick the next action." in first_message.content[0]["text"]


async def test_langgraph_backend_uses_structured_model_when_explicitly_enabled() -> None:
    from app.cognition.langgraph.agent_backend import LangGraphAgentBackend

    settings = Settings(
        agent_backend="langgraph",
        langgraph_reactor_structured_enabled=True,
    )

    class FakeStructuredModel:
        def __init__(self) -> None:
            self.structured_calls: list[dict] = []

        def with_structured_output(self, schema, *, method=None, include_raw=False):
            self.structured_calls.append(
                {"schema": schema, "method": method, "include_raw": include_raw}
            )
            return self

        async def ainvoke(self, prompt: str):
            return {
                "raw": {},
                "parsed": {
                    "action_type": "talk",
                    "target_agent_id": "bob",
                    "message": "Structured path works.",
                },
                "parsing_error": None,
            }

    model = FakeStructuredModel()
    backend = LangGraphAgentBackend(settings=settings, decision_model=model)
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
    assert result.message == "Structured path works."
    assert model.structured_calls[0]["method"] == "json_schema"
    assert model.structured_calls[0]["include_raw"] is True


async def test_langgraph_backend_can_disable_reactor_prompt_cache() -> None:
    from app.cognition.langgraph.agent_backend import LangGraphAgentBackend

    settings = Settings(
        agent_backend="langgraph",
        langgraph_reactor_prompt_cache_enabled=False,
    )

    class FakeTextModel:
        def __init__(self) -> None:
            self.prompts: list[object] = []

        async def ainvoke(self, prompt: object):
            self.prompts.append(prompt)
            return """
            {
              "action_type": "rest"
            }
            """

    model = FakeTextModel()
    backend = LangGraphAgentBackend(settings=settings, decision_model=model)
    invocation = AgentActionInvocation(
        agent_id="alice",
        prompt="Pick the next action.",
        context={"world": {"current_goal": "rest"}},
        max_turns=2,
        max_budget_usd=0.1,
        allowed_actions=["move", "talk", "work", "rest"],
    )

    result = await backend.decide_action(invocation)

    assert result.action_type == "rest"
    assert isinstance(model.prompts[0], str)


async def test_langgraph_backend_falls_back_when_model_errors() -> None:
    from app.cognition.langgraph.agent_backend import LangGraphAgentBackend

    class FailingModel:
        async def ainvoke(self, prompt: str):
            raise RuntimeError("model unavailable")

    backend = LangGraphAgentBackend(decision_model=FailingModel())
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


async def test_langgraph_backend_applies_decision_hook_fallback_and_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from app.cognition.claude.decision_utils import RuntimeDecision
    from app.cognition.langgraph.agent_backend import LangGraphAgentBackend

    class FailingModel:
        async def ainvoke(self, prompt: str):
            raise RuntimeError("connection error")

    backend = LangGraphAgentBackend(decision_model=FailingModel())
    backend.set_decision_hook(
        lambda world, nearby_agent_id, current_location_id, home_location_id, agent_id: (
            RuntimeDecision(
                action_type="talk",
                target_agent_id=nearby_agent_id,
                message="Fallback says hi.",
            )
        )
    )
    invocation = AgentActionInvocation(
        agent_id="alice",
        prompt="Pick the next action.",
        context={
            "world": {
                "current_goal": "talk",
                "nearby_agent_id": "bob",
                "current_location_id": "cafe",
                "home_location_id": "home",
            }
        },
        max_turns=2,
        max_budget_usd=0.1,
        allowed_actions=["move", "talk", "work", "rest"],
    )

    with caplog.at_level("WARNING"):
        result = await backend.decide_action(invocation)

    assert result.action_type == "talk"
    assert result.target_agent_id == "bob"
    assert result.message == "Fallback says hi."
    assert "LangGraph reactor fallback applied for alice: action=talk" in caplog.text


async def test_langgraph_backend_falls_back_to_text_json_when_structured_output_fails() -> None:
    from app.cognition.langgraph.agent_backend import LangGraphAgentBackend

    settings = Settings(
        agent_backend="langgraph",
        langgraph_reactor_structured_enabled=True,
    )

    class TextJsonFallbackModel:
        def __init__(self) -> None:
            self.calls = 0

        def with_structured_output(self, schema, *, method=None, include_raw=False):
            return self

        async def ainvoke(self, prompt: str):
            self.calls += 1
            if self.calls == 1:
                raise ValueError("structured output unsupported")
            return """
            好的，下面是结果：
            {
              "action_type": "talk",
              "target_agent_id": "bob",
              "message": "Fallback JSON works."
            }
            """

    backend = LangGraphAgentBackend(settings=settings, decision_model=TextJsonFallbackModel())
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
    assert result.message == "Fallback JSON works."


async def test_langgraph_backend_retries_transient_model_failures() -> None:
    from app.cognition.langgraph.agent_backend import LangGraphAgentBackend

    settings = Settings(
        agent_backend="langgraph",
        langgraph_reactor_structured_enabled=True,
    )

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
    backend = LangGraphAgentBackend(settings=settings, decision_model=model)
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


async def test_langgraph_backend_plan_day_returns_parsed_json() -> None:
    import asyncio

    from app.cognition.langgraph.agent_backend import LangGraphAgentBackend
    from app.cognition.types import PlanningInvocation

    class FakeTextResponse:
        def __init__(self, content: str) -> None:
            self.content = content
            self.usage_metadata = {"input_tokens": 19, "output_tokens": 13}

    class FakeTextModel:
        def __init__(self) -> None:
            self.prompts: list[str] = []

        async def ainvoke(self, prompt: str):
            self.prompts.append(prompt)
            await asyncio.sleep(0.01)
            return FakeTextResponse(
                '{"morning":"work","daytime":"talk","evening":"rest","intention":"stay visible"}'
            )

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

    model = FakeTextModel()
    backend = LangGraphAgentBackend(text_model=model)
    result = await backend.plan_day(
        PlanningInvocation(
            agent_id="alice",
            agent_name="Alice",
            prompt="Return a JSON plan",
            context={"world_time": "2026-03-02T06:00:00+00:00"},
        ),
        runtime_ctx=BackendExecutionContext(on_llm_call=on_llm_call),
    )

    assert result is not None
    assert result["morning"] == "work"
    assert model.prompts
    assert recorded[0]["agent_id"] == "alice"
    assert recorded[0]["task_type"] == "planner"
    assert recorded[0]["usage"] == {"input_tokens": 19, "output_tokens": 13}
    assert recorded[0]["cost"] == 0.0
    assert recorded[0]["duration"] > 0


async def test_langgraph_backend_reflect_day_returns_parsed_json() -> None:
    from app.cognition.langgraph.agent_backend import LangGraphAgentBackend
    from app.cognition.types import ReflectionInvocation

    class FakeTextResponse:
        def __init__(self, content: str) -> None:
            self.content = content
            self.usage_metadata = {"input_tokens": 9, "output_tokens": 21}

    class FakeTextModel:
        async def ainvoke(self, prompt: str):
            return FakeTextResponse(
                '{"reflection":"Good day","mood":"calm","key_person":"bob","tomorrow_intention":"rest"}'
            )

    backend = LangGraphAgentBackend(text_model=FakeTextModel())
    result = await backend.reflect_day(
        ReflectionInvocation(
            agent_id="alice",
            agent_name="Alice",
            prompt="Return a JSON reflection",
            context={"world_time": "2026-03-02T22:00:00+00:00"},
        )
    )

    assert result is not None
    assert result["mood"] == "calm"
    assert result["key_person"] == "bob"


async def test_langgraph_backend_logs_when_planner_falls_back(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from app.cognition.langgraph.agent_backend import LangGraphAgentBackend
    from app.cognition.types import PlanningInvocation

    class FailingTextModel:
        async def ainvoke(self, prompt: str):
            raise RuntimeError("connection error")

    backend = LangGraphAgentBackend(text_model=FailingTextModel())

    with caplog.at_level("WARNING"):
        result = await backend.plan_day(
            PlanningInvocation(
                agent_id="alice",
                agent_name="Alice",
                prompt="Return a JSON plan",
                context={"world_time": "2026-03-02T06:00:00+00:00"},
            )
        )

    assert result is None
    assert "LangGraph planner fallback applied for alice: result=None" in caplog.text


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
