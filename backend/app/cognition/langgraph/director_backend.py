from __future__ import annotations

from time import perf_counter
from typing import TYPE_CHECKING, Any, TypedDict
from uuid import uuid4

from langchain_core.runnables import Runnable
from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy

from app.cognition.claude.director_agent import DirectorAgent
from app.cognition.errors import UpstreamApiUnavailableError, is_upstream_api_unavailable_error
from app.cognition.langgraph.model_factory import build_langgraph_chat_model
from app.cognition.langgraph.observability import (
    LangGraphLoggingCallback,
    LangGraphTrace,
    notify_llm_call,
)
from app.cognition.protocols import ChatModelProtocol, DirectorIntervention
from app.cognition.types import DirectorDecisionInvocation
from app.infra.logging import get_logger
from app.infra.metrics import observe_director_decision
from app.infra.settings import Settings, get_settings

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel

logger = get_logger(__name__)


class _DirectorState(TypedDict, total=False):
    invocation: DirectorDecisionInvocation
    trace: LangGraphTrace
    result: DirectorIntervention | None
    candidates: list[dict[str, Any]]
    validation_error: str | None
    outcome: str


class LangGraphDirectorBackend:
    """LangGraph-compatible one-shot director backend.

    The director remains a stateless text-generation task. We reuse the
    existing DirectorAgent prompt construction and response parsing so the
    LangGraph backend only swaps the underlying model transport.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        text_model: BaseChatModel | ChatModelProtocol | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._agent = DirectorAgent(self._settings)
        self._enabled = (
            self._agent._config.enabled and self._settings.director_backend == "langgraph"
        )
        self._decision_interval = max(1, self._settings.director_decision_interval)
        self._text_model: BaseChatModel | ChatModelProtocol | None = (
            text_model or self._build_default_model()
        )
        graph = StateGraph(_DirectorState)
        graph.add_node("select_candidates", self._select_candidates_node)
        graph.add_node(
            "model_propose",
            self._propose_node,
            retry_policy=RetryPolicy(max_attempts=2),
        )
        graph.add_node("validate_proposal", self._validate_node)
        graph.add_node("repair_target", self._repair_target_node)
        graph.add_edge(START, "select_candidates")
        graph.add_conditional_edges(
            "select_candidates",
            self._route_after_selection,
            {"propose": "model_propose", "end": END},
        )
        graph.add_edge("model_propose", "validate_proposal")
        graph.add_conditional_edges(
            "validate_proposal",
            self._route_after_validation,
            {"repair": "repair_target", "end": END},
        )
        graph.add_edge("repair_target", END)
        self._graph = graph.compile()

    def is_enabled(self) -> bool:
        return self._enabled

    def should_decide(self, tick_no: int) -> bool:
        if not self._enabled:
            return False
        return tick_no % self._decision_interval == 0

    async def propose_intervention(
        self, invocation: DirectorDecisionInvocation
    ) -> DirectorIntervention | None:
        if not self._enabled:
            return None
        if self._text_model is None:
            msg = "LangGraph director model is not configured or unavailable"
            raise UpstreamApiUnavailableError(msg)

        context = invocation.context
        runtime_ctx = invocation.runtime_ctx
        graph_run_id = uuid4()
        trace = LangGraphTrace(
            trace_id=str(graph_run_id),
            graph_run_id=graph_run_id,
            graph_name="director_control",
            simulation_run_id=runtime_ctx.run_id if runtime_ctx is not None else context.run_id,
            tick_no=runtime_ctx.tick_no if runtime_ctx is not None else context.current_tick,
            agent_id=None,
            task_type="director",
            provider=self._settings.llm_provider,
            model=self._settings.director_agent_model or self._settings.llm_model,
        )
        state = await self._graph.ainvoke(
            {
                "invocation": invocation,
                "trace": trace,
                "result": None,
                "candidates": [],
                "validation_error": None,
                "outcome": "noop",
            },
            config=trace.runnable_config(LangGraphLoggingCallback(trace)),
        )
        observe_director_decision(outcome=state.get("outcome", "noop"))
        return state["result"]

    async def _select_candidates_node(self, state: _DirectorState) -> dict[str, Any]:
        candidates = self._agent._select_support_agents(state["invocation"].context)
        return {
            "candidates": candidates,
            "outcome": "candidate_selected" if candidates else "no_candidates",
        }

    @staticmethod
    def _route_after_selection(state: _DirectorState) -> str:
        return "propose" if state.get("candidates") else "end"

    async def _propose_node(self, state: _DirectorState) -> dict[str, Any]:
        result = await self._propose_once(
            state["invocation"], state["trace"], state.get("candidates") or []
        )
        return {"result": result}

    @staticmethod
    async def _validate_node(state: _DirectorState) -> dict[str, Any]:
        result = state.get("result")
        if result is None:
            return {"validation_error": None, "outcome": "noop"}
        candidate_ids = {candidate.get("id") for candidate in state.get("candidates") or []}
        if result.target_agent_ids and all(
            target_id in candidate_ids for target_id in result.target_agent_ids
        ):
            return {"validation_error": None, "outcome": "proposed"}
        return {"validation_error": "unavailable_target", "outcome": "invalid_target"}

    @staticmethod
    def _route_after_validation(state: _DirectorState) -> str:
        return "repair" if state.get("validation_error") else "end"

    @staticmethod
    async def _repair_target_node(state: _DirectorState) -> dict[str, Any]:
        result = state.get("result")
        candidates = state.get("candidates") or []
        if result is None or not candidates:
            return {"result": None, "outcome": "invalid_target"}
        result.target_agent_ids = [candidates[0]["id"]]
        return {
            "result": result,
            "validation_error": None,
            "outcome": "repaired",
        }

    async def _propose_once(
        self,
        invocation: DirectorDecisionInvocation,
        trace: LangGraphTrace,
        support_agents: list[dict[str, Any]],
    ) -> DirectorIntervention | None:
        context = invocation.context
        if not support_agents or context.assessment.subject_agent_id is None:
            return None

        prompt = self._agent._build_decision_prompt(
            context, support_agents, invocation.recent_goals
        )
        full_prompt = f"{prompt}\n\n重要：你必须只返回一个有效的 JSON 对象，不要有其他任何文本。"
        started_at = perf_counter()
        logger.debug(
            "LangGraph director decision started",
            extra={"event": "langgraph_director_started", **trace.fields()},
        )

        try:
            if isinstance(self._text_model, Runnable):
                response = await self._text_model.ainvoke(
                    full_prompt,
                    config=trace.runnable_config(),
                )
            else:
                response = await self._text_model.ainvoke(full_prompt)
        except Exception as exc:
            duration_ms = int((perf_counter() - started_at) * 1000)
            self._record_llm_call(
                invocation,
                trace=trace,
                response=None,
                duration_ms=duration_ms,
                status="error",
                exception_type=type(exc).__name__,
                failure_reason="model_error",
            )
            logger.warning(
                "LangGraph director decision failed",
                extra={
                    "event": "langgraph_director_failed",
                    **trace.fields(),
                    "status": "error",
                    "duration_ms": duration_ms,
                    "exception_type": type(exc).__name__,
                },
            )
            if is_upstream_api_unavailable_error(exc):
                raise UpstreamApiUnavailableError(str(exc)) from exc
            raise

        duration_ms = int((perf_counter() - started_at) * 1000)
        content = self._extract_text_content(response)
        status = "success" if content else "invalid_output"
        self._record_llm_call(
            invocation,
            trace=trace,
            response=response,
            duration_ms=duration_ms,
            status=status,
            failure_reason=None if content else "empty_content",
        )
        result = self._agent._parse_response(
            content,
            context,
            support_agents,
        )
        logger.debug(
            "LangGraph director decision completed",
            extra={
                "event": "langgraph_director_completed",
                **trace.fields(),
                "status": status,
                "duration_ms": duration_ms,
                "intervention_proposed": result is not None,
            },
        )
        return result

    def _build_default_model(self) -> BaseChatModel | None:
        model_name = self._settings.director_agent_model or self._settings.llm_model
        return build_langgraph_chat_model(self._settings, model_name=model_name)

    def _extract_text_content(self, response: object) -> str:
        content = getattr(response, "content", response)
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str):
                        parts.append(text)
                else:
                    text = getattr(item, "text", None)
                    if isinstance(text, str):
                        parts.append(text)
            return "\n".join(parts).strip()
        return ""

    def _record_llm_call(
        self,
        invocation: DirectorDecisionInvocation,
        *,
        trace: LangGraphTrace,
        response: Any,
        duration_ms: int,
        status: str,
        exception_type: str | None = None,
        failure_reason: str | None = None,
    ) -> None:
        callback = (
            invocation.runtime_ctx.on_llm_call if invocation.runtime_ctx is not None else None
        )
        if callback is None:
            return
        usage = getattr(response, "usage_metadata", None)
        if usage is None and isinstance(response, dict):
            usage = response.get("usage_metadata")
        notify_llm_call(
            callback,
            agent_id="director",
            task_type="director",
            usage=usage,
            total_cost_usd=self._extract_total_cost_usd(response, usage),
            duration_ms=duration_ms,
            status=status,
            trace_id=trace.trace_id,
            node_name="director_decide",
            attempt_no=1,
            exception_type=exception_type,
            failure_reason=failure_reason,
            fallback_from=None,
        )

    @staticmethod
    def _extract_total_cost_usd(response: Any, usage: Any) -> float | None:
        for source in (usage, getattr(response, "response_metadata", None)):
            if not isinstance(source, dict):
                continue
            for key in ("total_cost_usd", "cost_usd"):
                value = source.get(key)
                if isinstance(value, int | float):
                    return float(value)
        return None
