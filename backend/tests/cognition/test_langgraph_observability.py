from __future__ import annotations

from unittest.mock import Mock, patch
from uuid import uuid4

from app.cognition.langgraph.agent_backend import LangGraphAgentBackend
from app.cognition.langgraph.observability import LangGraphTrace
from app.cognition.types import AgentActionInvocation, BackendExecutionContext
from app.infra.settings import Settings
from app.sim.llm_call_collector import LlmCallCollector


def _invocation() -> AgentActionInvocation:
    return AgentActionInvocation(
        agent_id="alice",
        prompt="Pick the next action.",
        context={"world": {"current_goal": "talk"}},
        max_turns=2,
        max_budget_usd=0.1,
        allowed_actions=["move", "talk", "work", "rest"],
    )


async def test_graph_emits_native_run_and_node_callbacks() -> None:
    class FakeTextModel:
        async def ainvoke(self, prompt: str):
            return '{"action_type":"rest"}'

    observed_logger = Mock()
    backend = LangGraphAgentBackend(decision_model=FakeTextModel())

    with patch("app.cognition.langgraph.observability.logger", observed_logger):
        await backend.decide_action(_invocation())

    calls = observed_logger.debug.call_args_list + observed_logger.log.call_args_list
    events = [call.kwargs["extra"]["event"] for call in calls]
    assert "langgraph_run_started" in events
    assert "langgraph_node_started" in events
    assert "langgraph_node_completed" in events
    assert "langgraph_run_completed" in events


async def test_retry_records_each_attempt_under_one_trace() -> None:
    class FlakyStructuredModel:
        def __init__(self) -> None:
            self.calls = 0

        def with_structured_output(self, schema):
            return self

        async def ainvoke(self, prompt: str):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("temporary model failure")
            return {"action_type": "rest"}

    collector = LlmCallCollector()
    callback = collector.build_callback(
        run_id="run-1",
        db_agent_id="db-alice",
        tick_no=9,
        backend="langgraph",
    )
    backend = LangGraphAgentBackend(
        settings=Settings(
            agent_backend="langgraph",
            langgraph_reactor_structured_enabled=True,
        ),
        decision_model=FlakyStructuredModel(),
    )

    await backend.decide_action(
        _invocation(),
        runtime_ctx=BackendExecutionContext(
            run_id="run-1",
            tick_no=9,
            on_llm_call=callback,
        ),
    )

    assert [record.status for record in collector.records] == ["error", "success"]
    assert [record.attempt_no for record in collector.records] == [1, 2]
    assert len({record.trace_id for record in collector.records}) == 1
    assert all(record.node_name == "model_decide" for record in collector.records)
    assert collector.records[0].exception_type == "RuntimeError"


async def test_structured_fallback_records_both_model_paths() -> None:
    class FallbackModel:
        def __init__(self) -> None:
            self.calls = 0

        def with_structured_output(self, schema, **kwargs):
            return self

        async def ainvoke(self, prompt: str):
            self.calls += 1
            if self.calls == 1:
                raise ValueError("structured output unavailable")
            return '{"action_type":"rest"}'

    collector = LlmCallCollector()
    backend = LangGraphAgentBackend(
        settings=Settings(
            agent_backend="langgraph",
            langgraph_reactor_structured_enabled=True,
        ),
        decision_model=FallbackModel(),
    )

    await backend.decide_action(
        _invocation(),
        runtime_ctx=BackendExecutionContext(
            run_id="run-1",
            tick_no=9,
            on_llm_call=collector.build_callback(
                run_id="run-1",
                db_agent_id="db-alice",
                tick_no=9,
                backend="langgraph",
            ),
        ),
    )

    assert [record.status for record in collector.records] == ["error", "success"]
    assert collector.records[1].fallback_from == "structured"
    assert len({record.trace_id for record in collector.records}) == 1


def test_trace_config_separates_graph_and_simulation_run_ids() -> None:
    graph_run_id = uuid4()
    trace = LangGraphTrace(
        trace_id=str(graph_run_id),
        graph_run_id=graph_run_id,
        graph_name="agent_reactor",
        simulation_run_id="simulation-1",
        tick_no=3,
        agent_id="alice",
        task_type="reactor",
        provider="openai",
        model="model-1",
    )

    config = trace.runnable_config()

    assert config["run_id"] == graph_run_id
    assert config["metadata"]["simulation_run_id"] == "simulation-1"
    assert config["metadata"]["graph_run_id"] == str(graph_run_id)
