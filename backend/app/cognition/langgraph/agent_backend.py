from __future__ import annotations

import json
from time import perf_counter
from typing import TYPE_CHECKING, Any, TypedDict
from uuid import uuid4

from langchain_core.messages import HumanMessage
from langchain_core.runnables import Runnable
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import RetryPolicy
from pydantic import BaseModel, Field

from app.agent.prompt_loader import PromptLoader
from app.cognition.errors import (
    UpstreamApiUnavailableError,
    is_upstream_api_unavailable_error,
)
from app.cognition.langgraph.model_factory import build_langgraph_chat_model
from app.cognition.langgraph.observability import (
    LangGraphLoggingCallback,
    LangGraphTrace,
    notify_llm_call,
)
from app.cognition.protocols import ChatModelProtocol, StructuredModelProtocol
from app.cognition.types import (
    AgentActionInvocation,
    AgentDecisionResult,
    BackendExecutionContext,
    PlanningInvocation,
    ReflectionInvocation,
)
from app.infra.logging import get_logger
from app.infra.metrics import observe_langgraph_fallback, observe_langgraph_retry
from app.infra.settings import Settings, get_settings

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel

logger = get_logger(__name__)


class _StructuredDecision(BaseModel):
    action_type: str
    target_location_id: str | None = None
    target_agent_id: str | None = None
    message: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    directive_id: str | None = None
    directive_disposition: str | None = None
    directive_reason: str | None = None


class _DecisionState(TypedDict):
    invocation: AgentActionInvocation
    result: AgentDecisionResult | None


class _DecisionContext(TypedDict):
    runtime_ctx: BackendExecutionContext | None
    trace: LangGraphTrace


class LangGraphAgentBackend:
    """Minimal LangGraph-backed reactor stub.

    This first version only supports decide_action(). It keeps planner and
    reflector disabled so the backend can be integrated incrementally.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        decision_model: BaseChatModel | ChatModelProtocol | None = None,
        text_model: BaseChatModel | ChatModelProtocol | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        default_model = (
            self._build_default_model() if decision_model is None and text_model is None else None
        )
        self._decision_model: BaseChatModel | ChatModelProtocol | None = (
            decision_model or default_model
        )
        self._text_model: BaseChatModel | ChatModelProtocol | None = (
            text_model or decision_model or default_model
        )
        graph = StateGraph(_DecisionState, context_schema=_DecisionContext)
        graph.add_node(
            "model_decide",
            self._model_decide_node,
            retry_policy=self._build_model_retry_policy(),
        )
        graph.add_edge(START, "model_decide")
        graph.add_edge("model_decide", END)
        self._graph = graph.compile()

    async def decide_action(
        self,
        invocation: AgentActionInvocation,
        runtime_ctx: BackendExecutionContext | None = None,
    ) -> AgentDecisionResult:
        if self._decision_model is None:
            msg = "LangGraph reactor model is not configured or unavailable"
            raise UpstreamApiUnavailableError(msg)

        started_at = perf_counter()
        trace = self._build_trace(
            graph_name="agent_reactor",
            agent_id=invocation.agent_id,
            task_type="reactor",
            runtime_ctx=runtime_ctx,
        )
        callback = LangGraphLoggingCallback(trace)
        try:
            state = await self._graph.ainvoke(
                {
                    "invocation": invocation,
                    "result": None,
                },
                config=trace.runnable_config(callback),
                context={"runtime_ctx": runtime_ctx, "trace": trace},
            )
        except UpstreamApiUnavailableError:
            raise
        except Exception:
            raise
        result = state["result"] or AgentDecisionResult(action_type="rest")
        logger.debug(
            "LangGraph reactor decision completed",
            extra={
                "event": "langgraph_reactor_completed",
                **trace.fields(),
                "status": "success",
                "duration_ms": int((perf_counter() - started_at) * 1000),
                "action_type": result.action_type,
                "target_agent_id": result.target_agent_id,
                "target_location_id": result.target_location_id,
            },
        )
        return result

    async def plan_day(
        self,
        invocation: PlanningInvocation,
        runtime_ctx: BackendExecutionContext | None = None,
    ) -> dict | None:
        return await self._run_text_task(
            agent_id=invocation.agent_id,
            task="planner",
            prompt=invocation.prompt,
            runtime_ctx=runtime_ctx,
        )

    async def reflect_day(
        self,
        invocation: ReflectionInvocation,
        runtime_ctx: BackendExecutionContext | None = None,
    ) -> dict | None:
        return await self._run_text_task(
            agent_id=invocation.agent_id,
            task="reflector",
            prompt=invocation.prompt,
            runtime_ctx=runtime_ctx,
        )

    async def _model_decide_node(
        self,
        state: _DecisionState,
        runtime: Runtime[_DecisionContext],
    ) -> dict[str, AgentDecisionResult]:
        invocation = state["invocation"]
        runtime_ctx = runtime.context.get("runtime_ctx")
        trace = runtime.context["trace"]
        execution_info = getattr(runtime, "execution_info", None)
        attempt_no = getattr(execution_info, "node_attempt", 1)
        try:
            fallback_from = None
            if self._settings.langgraph_reactor_structured_enabled:
                result = await self._run_structured_reactor_decision(
                    invocation,
                    runtime_ctx,
                    trace=trace,
                    attempt_no=attempt_no,
                )
                if result is not None:
                    return {"result": result}
                fallback_from = "structured"
                self._log_fallback(trace, reason="unusable_output")

            result = await self._run_text_reactor_decision(
                invocation,
                runtime_ctx,
                trace=trace,
                attempt_no=attempt_no,
                fallback_from=fallback_from,
            )
            if result is not None:
                return {"result": result}

            msg = f"LangGraph reactor returned no usable decision for {invocation.agent_id}"
            raise RuntimeError(msg)
        except Exception as exc:
            if isinstance(exc, RuntimeError) and attempt_no < 2:
                observe_langgraph_retry(
                    graph=trace.graph_name,
                    node="model_decide",
                    exception_type=type(exc).__name__,
                )
                logger.warning(
                    "LangGraph node retry scheduled",
                    extra={
                        "event": "langgraph_node_retry_scheduled",
                        **trace.fields(),
                        "graph_node": "model_decide",
                        "node_attempt": attempt_no,
                        "next_attempt": attempt_no + 1,
                        "exception_type": type(exc).__name__,
                    },
                )
            raise

    def _build_default_model(self) -> BaseChatModel | None:
        return build_langgraph_chat_model(self._settings)

    def decision_concurrency_limit(self) -> int | None:
        limit = self._settings.langgraph_reactor_max_concurrency
        return limit if limit > 0 else None

    async def _run_text_task(
        self,
        *,
        agent_id: str,
        task: str,
        prompt: str,
        runtime_ctx: BackendExecutionContext | None,
    ) -> dict[str, Any] | None:
        if self._text_model is None:
            msg = f"LangGraph {task} model is not configured or unavailable"
            raise UpstreamApiUnavailableError(msg)
        started_at = perf_counter()
        trace = self._build_trace(
            graph_name=f"agent_{task}",
            agent_id=agent_id,
            task_type=task,
            runtime_ctx=runtime_ctx,
        )
        try:
            response = await self._invoke_model(
                self._text_model,
                f"{prompt}\n\n重要：只返回 JSON，不要有任何其他文字。",
                config=trace.runnable_config(),
            )
            duration_ms = int((perf_counter() - started_at) * 1000)
        except Exception as exc:
            duration_ms = int((perf_counter() - started_at) * 1000)
            self._record_llm_call(
                runtime_ctx,
                agent_id=agent_id,
                task_type=task,
                response=None,
                duration_ms=duration_ms,
                status="error",
                trace=trace,
                exception_type=type(exc).__name__,
                failure_reason="model_error",
            )
            self._raise_on_upstream_unavailable(exc)
            logger.warning(
                "LangGraph text task failed",
                extra={
                    "event": "langgraph_text_task_failed",
                    **trace.fields(),
                    "status": "error",
                    "duration_ms": duration_ms,
                    "exception_type": type(exc).__name__,
                },
            )
            raise

        content = self._extract_text_content(response)
        if not content:
            self._record_llm_call(
                runtime_ctx,
                agent_id=agent_id,
                task_type=task,
                response=response,
                duration_ms=duration_ms,
                status="invalid_output",
                trace=trace,
                failure_reason="empty_content",
            )
            msg = f"LangGraph {task} returned empty response for {agent_id}"
            raise RuntimeError(msg)
        parsed = PromptLoader.extract_json_from_text(content)
        if parsed is None:
            self._record_llm_call(
                runtime_ctx,
                agent_id=agent_id,
                task_type=task,
                response=response,
                duration_ms=duration_ms,
                status="invalid_output",
                trace=trace,
                failure_reason="non_json",
            )
            logger.warning(
                "LangGraph response was not valid JSON",
                extra={
                    "event": "llm_response_invalid",
                    **trace.fields(),
                    "status": "invalid_output",
                    "failure_reason": "non_json",
                    "duration_ms": duration_ms,
                    "response_length": len(content),
                },
            )
            msg = f"LangGraph {task} returned non-JSON for {agent_id}"
            raise ValueError(msg)
        self._record_llm_call(
            runtime_ctx,
            agent_id=agent_id,
            task_type=task,
            response=response,
            duration_ms=duration_ms,
            status="success",
            trace=trace,
        )
        logger.debug(
            "LangGraph text task completed",
            extra={
                "event": "langgraph_text_task_completed",
                **trace.fields(),
                "status": "success",
                "duration_ms": duration_ms,
                "response_keys": sorted(parsed.keys()) if isinstance(parsed, dict) else None,
            },
        )
        return parsed

    def _build_model_retry_policy(self) -> RetryPolicy:
        return RetryPolicy(
            max_attempts=2,
            retry_on=lambda exc: isinstance(exc, RuntimeError),
        )

    def _build_model_prompt(self, invocation: AgentActionInvocation) -> str:
        context_json = json.dumps(invocation.context, ensure_ascii=False, sort_keys=True)
        allowed_actions = ", ".join(invocation.allowed_actions)
        static_prompt, dynamic_context = self._split_embedded_runtime_context(
            invocation.prompt, context_json
        )
        return (
            f"{static_prompt}\n\n"
            f"Allowed actions: {allowed_actions}\n\n"
            "Return only the structured action decision.\n\n"
            f"Agent context JSON:\n{dynamic_context}"
        )

    def _split_reactor_prompt(self, invocation: AgentActionInvocation) -> tuple[str, str]:
        prompt = self._build_text_json_prompt(invocation)
        # Split point: "Agent context JSON:\n" followed by the dynamic context
        # Everything before this marker is stable (prompt, actions, instructions, schema)
        # Everything after is dynamic (world state that changes every tick)
        marker = "Agent context JSON:\n"
        if marker not in prompt:
            return prompt, ""
        stable_prefix, dynamic_suffix = prompt.split(marker, 1)
        # Include "Agent context JSON:" in stable prefix (without trailing newline)
        # dynamic_suffix is just the context JSON
        return (stable_prefix + "Agent context JSON:").rstrip(), dynamic_suffix.strip()

    def _build_reactor_messages(
        self, invocation: AgentActionInvocation
    ) -> list[HumanMessage] | str:
        if self._settings.llm_provider != "anthropic":
            return self._build_text_json_prompt(invocation)
        if not self._settings.langgraph_reactor_prompt_cache_enabled:
            return self._build_text_json_prompt(invocation)

        stable_prefix, dynamic_suffix = self._split_reactor_prompt(invocation)
        content: list[dict[str, Any]] = []
        if stable_prefix:
            content.append(
                {
                    "type": "text",
                    "text": stable_prefix,
                    "cache_control": {"type": "ephemeral"},
                }
            )
        if dynamic_suffix:
            content.append({"type": "text", "text": dynamic_suffix})
        logger.debug(
            "LangGraph reactor input prepared",
            extra={
                "event": "langgraph_reactor_input_prepared",
                "backend": "langgraph",
                "agent_id": invocation.agent_id,
                "input_mode": "message_blocks",
                "cache_enabled": self._settings.langgraph_reactor_prompt_cache_enabled,
                "stable_chars": len(stable_prefix),
                "dynamic_chars": len(dynamic_suffix),
            },
        )
        return [
            HumanMessage(
                content=content or [{"type": "text", "text": stable_prefix or dynamic_suffix}]
            )
        ]

    async def _run_structured_reactor_decision(
        self,
        invocation: AgentActionInvocation,
        runtime_ctx: BackendExecutionContext | None,
        *,
        trace: LangGraphTrace,
        attempt_no: int,
    ) -> AgentDecisionResult | None:
        started_at = perf_counter()
        try:
            structured_model = self._build_structured_decision_model()
            response = await self._invoke_model(
                structured_model,
                self._build_reactor_messages(invocation),
            )
        except Exception as exc:
            duration_ms = int((perf_counter() - started_at) * 1000)
            self._record_llm_call(
                runtime_ctx,
                agent_id=invocation.agent_id,
                task_type="reactor",
                response=None,
                duration_ms=duration_ms,
                status="error",
                trace=trace,
                node_name="model_decide",
                attempt_no=attempt_no,
                exception_type=type(exc).__name__,
                failure_reason="model_error",
            )
            self._raise_on_upstream_unavailable(exc)
            logger.warning(
                "LangGraph structured reactor path failed",
                extra={
                    "event": "langgraph_reactor_path_failed",
                    **trace.fields(),
                    "path": "structured",
                    "status": "error",
                    "duration_ms": duration_ms,
                    "node_attempt": attempt_no,
                    "exception_type": type(exc).__name__,
                },
            )
            if isinstance(exc, RuntimeError):
                raise
            return None

        duration_ms = int((perf_counter() - started_at) * 1000)
        raw_response = response.get("raw") if self._is_structured_wrapper(response) else response
        parsed = self._extract_structured_response(response)
        if parsed is None:
            self._record_llm_call(
                runtime_ctx,
                agent_id=invocation.agent_id,
                task_type="reactor",
                response=raw_response,
                duration_ms=duration_ms,
                status="invalid_output",
                trace=trace,
                node_name="model_decide",
                attempt_no=attempt_no,
                failure_reason="structured_parse_error",
            )
            logger.debug(
                "LangGraph structured reactor path returned invalid output",
                extra={
                    "event": "langgraph_reactor_path_completed",
                    **trace.fields(),
                    "path": "structured",
                    "status": "invalid_output",
                    "duration_ms": duration_ms,
                    "node_attempt": attempt_no,
                    "failure_reason": "structured_parse_error",
                },
            )
            return None
        result = self._coerce_model_result(parsed, invocation.allowed_actions)
        status = "success" if result is not None else "invalid_output"
        self._record_llm_call(
            runtime_ctx,
            agent_id=invocation.agent_id,
            task_type="reactor",
            response=raw_response,
            duration_ms=duration_ms,
            status=status,
            trace=trace,
            node_name="model_decide",
            attempt_no=attempt_no,
            failure_reason=None if result is not None else "invalid_decision",
        )
        logger.debug(
            "LangGraph structured reactor path completed",
            extra={
                "event": "langgraph_reactor_path_completed",
                **trace.fields(),
                "path": "structured",
                "status": status,
                "duration_ms": duration_ms,
                "node_attempt": attempt_no,
                "action_type": result.action_type if result is not None else None,
                "failure_reason": None if result is not None else "invalid_decision",
            },
        )
        return result

    async def _run_text_reactor_decision(
        self,
        invocation: AgentActionInvocation,
        runtime_ctx: BackendExecutionContext | None,
        *,
        trace: LangGraphTrace,
        attempt_no: int,
        fallback_from: str | None,
    ) -> AgentDecisionResult | None:
        started_at = perf_counter()
        try:
            response = await self._invoke_model(
                self._decision_model,
                self._build_reactor_messages(invocation),
            )
        except Exception as exc:
            duration_ms = int((perf_counter() - started_at) * 1000)
            self._record_llm_call(
                runtime_ctx,
                agent_id=invocation.agent_id,
                task_type="reactor",
                response=None,
                duration_ms=duration_ms,
                status="error",
                trace=trace,
                node_name="model_decide",
                attempt_no=attempt_no,
                exception_type=type(exc).__name__,
                failure_reason="model_error",
                fallback_from=fallback_from,
            )
            self._raise_on_upstream_unavailable(exc)
            logger.warning(
                "LangGraph text reactor path failed",
                extra={
                    "event": "langgraph_reactor_path_failed",
                    **trace.fields(),
                    "path": "text",
                    "status": "error",
                    "duration_ms": duration_ms,
                    "node_attempt": attempt_no,
                    "exception_type": type(exc).__name__,
                    "fallback_from": fallback_from,
                },
            )
            raise

        duration_ms = int((perf_counter() - started_at) * 1000)
        content = self._extract_text_content(response)
        if not content:
            self._record_llm_call(
                runtime_ctx,
                agent_id=invocation.agent_id,
                task_type="reactor",
                response=response,
                duration_ms=duration_ms,
                status="invalid_output",
                trace=trace,
                node_name="model_decide",
                attempt_no=attempt_no,
                failure_reason="empty_content",
                fallback_from=fallback_from,
            )
            logger.debug(
                "LangGraph text reactor path returned empty output",
                extra={
                    "event": "langgraph_reactor_path_completed",
                    **trace.fields(),
                    "path": "text",
                    "status": "invalid_output",
                    "duration_ms": duration_ms,
                    "node_attempt": attempt_no,
                    "failure_reason": "empty_content",
                    "fallback_from": fallback_from,
                },
            )
            return None
        parsed = PromptLoader.extract_json_from_text(content)
        if not isinstance(parsed, dict):
            self._record_llm_call(
                runtime_ctx,
                agent_id=invocation.agent_id,
                task_type="reactor",
                response=response,
                duration_ms=duration_ms,
                status="invalid_output",
                trace=trace,
                node_name="model_decide",
                attempt_no=attempt_no,
                failure_reason="non_json",
                fallback_from=fallback_from,
            )
            logger.debug(
                "LangGraph text reactor path returned non-JSON output",
                extra={
                    "event": "langgraph_reactor_path_completed",
                    **trace.fields(),
                    "path": "text",
                    "status": "invalid_output",
                    "duration_ms": duration_ms,
                    "node_attempt": attempt_no,
                    "failure_reason": "non_json",
                    "fallback_from": fallback_from,
                },
            )
            return None
        result = self._coerce_model_result(parsed, invocation.allowed_actions)
        status = "success" if result is not None else "invalid_output"
        self._record_llm_call(
            runtime_ctx,
            agent_id=invocation.agent_id,
            task_type="reactor",
            response=response,
            duration_ms=duration_ms,
            status=status,
            trace=trace,
            node_name="model_decide",
            attempt_no=attempt_no,
            failure_reason=None if result is not None else "invalid_decision",
            fallback_from=fallback_from,
        )
        logger.debug(
            "LangGraph text reactor path completed",
            extra={
                "event": "langgraph_reactor_path_completed",
                **trace.fields(),
                "path": "text",
                "status": status,
                "duration_ms": duration_ms,
                "node_attempt": attempt_no,
                "action_type": result.action_type if result is not None else None,
                "failure_reason": None if result is not None else "invalid_decision",
                "fallback_from": fallback_from,
            },
        )
        return result

    def _build_text_json_prompt(self, invocation: AgentActionInvocation) -> str:
        schema_json = json.dumps(
            _StructuredDecision.model_json_schema(), ensure_ascii=False, indent=2
        )
        context_json = json.dumps(invocation.context, ensure_ascii=False, sort_keys=True)
        allowed_actions = ", ".join(invocation.allowed_actions)
        static_prompt, dynamic_context = self._split_embedded_runtime_context(
            invocation.prompt, context_json
        )
        return (
            f"{static_prompt}\n\n"
            f"Allowed actions: {allowed_actions}\n\n"
            "Return only the structured action decision.\n\n"
            "If native structured output is unavailable, return exactly one JSON object "
            "matching this schema and no additional text.\n"
            f"{schema_json}\n\n"
            f"Agent context JSON:\n{dynamic_context}"
        )

    @staticmethod
    def _split_embedded_runtime_context(prompt: str, context_json: str) -> tuple[str, str]:
        dynamic_marker = "\n# 动态决策上下文\n"
        static_prompt, separator, dynamic_context = prompt.partition(dynamic_marker)
        if separator:
            return static_prompt.rstrip(), dynamic_context.strip()

        legacy_marker = "\n# 运行上下文\n```json\n"
        static_prompt, separator, embedded_json = prompt.partition(legacy_marker)
        if separator:
            return static_prompt.rstrip(), embedded_json.removesuffix("\n```").strip()
        return prompt, context_json

    def _build_structured_decision_model(self) -> StructuredModelProtocol:
        try:
            return self._decision_model.with_structured_output(
                _StructuredDecision,
                method="json_schema",
                include_raw=True,
            )
        except TypeError:
            return self._decision_model.with_structured_output(_StructuredDecision)

    def _is_structured_wrapper(self, response: Any) -> bool:
        return isinstance(response, dict) and {
            "raw",
            "parsed",
            "parsing_error",
        }.issubset(response.keys())

    def _extract_structured_response(self, response: Any) -> Any | None:
        if self._is_structured_wrapper(response):
            if response.get("parsing_error") is not None:
                return None
            return response.get("parsed")
        return response

    def _coerce_model_result(
        self,
        response: _StructuredDecision | dict[str, Any],
        allowed_actions: list[str],
    ) -> AgentDecisionResult | None:
        data = response.model_dump() if isinstance(response, BaseModel) else dict(response)
        action_type = data.get("action_type")
        if not isinstance(action_type, str):
            return None
        if allowed_actions and action_type not in allowed_actions:
            return None
        if action_type == "move" and not data.get("target_location_id"):
            return None
        if action_type == "talk":
            if not data.get("target_agent_id"):
                return None
            message = data.get("message")
            if not isinstance(message, str) or not message.strip():
                return None
        return AgentDecisionResult(
            action_type=action_type,
            target_location_id=data.get("target_location_id"),
            target_agent_id=data.get("target_agent_id"),
            message=data.get("message"),
            payload=dict(data.get("payload") or {}),
            directive_id=data.get("directive_id"),
            directive_disposition=data.get("directive_disposition"),
            directive_reason=data.get("directive_reason"),
        )

    def _extract_text_content(self, response: Any) -> str:
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

    def _raise_on_upstream_unavailable(self, exc: Exception) -> None:
        if not is_upstream_api_unavailable_error(exc):
            return
        raise UpstreamApiUnavailableError(str(exc)) from exc

    def _record_llm_call(
        self,
        runtime_ctx: BackendExecutionContext | None,
        *,
        agent_id: str,
        task_type: str,
        response: Any,
        duration_ms: int,
        status: str,
        trace: LangGraphTrace,
        node_name: str | None = None,
        attempt_no: int = 1,
        exception_type: str | None = None,
        failure_reason: str | None = None,
        fallback_from: str | None = None,
    ) -> None:
        if runtime_ctx is None or runtime_ctx.on_llm_call is None:
            return
        usage = getattr(response, "usage_metadata", None)
        if usage is None and isinstance(response, dict):
            usage = response.get("usage_metadata")
        input_token_details = usage.get("input_token_details") if isinstance(usage, dict) else None
        cache_read = (
            input_token_details.get("cache_read") if isinstance(input_token_details, dict) else None
        )
        cache_creation = (
            input_token_details.get("cache_creation")
            if isinstance(input_token_details, dict)
            else None
        )
        logger.debug(
            "LangGraph LLM call observed",
            extra={
                "event": "llm_call_observed",
                **trace.fields(),
                "status": status,
                "response_type": type(response).__name__ if response is not None else None,
                "usage_present": usage is not None,
                "input_tokens": usage.get("input_tokens") if isinstance(usage, dict) else None,
                "output_tokens": usage.get("output_tokens") if isinstance(usage, dict) else None,
                "cache_read_tokens": cache_read,
                "cache_creation_tokens": cache_creation,
                "duration_ms": duration_ms,
                "graph_node": node_name,
                "node_attempt": attempt_no,
                "exception_type": exception_type,
                "failure_reason": failure_reason,
                "fallback_from": fallback_from,
            },
        )
        notify_llm_call(
            runtime_ctx.on_llm_call,
            agent_id=agent_id,
            task_type=task_type,
            usage=usage,
            total_cost_usd=self._extract_total_cost_usd(response, usage),
            duration_ms=duration_ms,
            status=status,
            trace_id=trace.trace_id,
            node_name=node_name,
            attempt_no=attempt_no,
            exception_type=exception_type,
            failure_reason=failure_reason,
            fallback_from=fallback_from,
        )

    def _build_trace(
        self,
        *,
        graph_name: str,
        agent_id: str | None,
        task_type: str,
        runtime_ctx: BackendExecutionContext | None,
    ) -> LangGraphTrace:
        graph_run_id = uuid4()
        return LangGraphTrace(
            trace_id=str(graph_run_id),
            graph_run_id=graph_run_id,
            graph_name=graph_name,
            simulation_run_id=runtime_ctx.run_id if runtime_ctx is not None else None,
            tick_no=runtime_ctx.tick_no if runtime_ctx is not None else None,
            agent_id=agent_id,
            task_type=task_type,
            provider=self._settings.llm_provider,
            model=self._settings.llm_model,
        )

    async def _invoke_model(
        self,
        model: Any,
        model_input: Any,
        *,
        config: dict[str, Any] | None = None,
    ) -> Any:
        if config is not None and isinstance(model, Runnable):
            return await model.ainvoke(model_input, config=config)
        return await model.ainvoke(model_input)

    @staticmethod
    def _log_fallback(trace: LangGraphTrace, *, reason: str) -> None:
        observe_langgraph_fallback(
            task_type=trace.task_type,
            from_path="structured",
            to_path="text",
            reason=reason,
        )
        logger.info(
            "LangGraph model path fallback selected",
            extra={
                "event": "langgraph_model_fallback",
                **trace.fields(),
                "from_path": "structured",
                "to_path": "text",
                "reason": reason,
            },
        )

    @staticmethod
    def _extract_total_cost_usd(response: Any, usage: Any) -> float | None:
        sources = [usage, getattr(response, "response_metadata", None)]
        for source in sources:
            if not isinstance(source, dict):
                continue
            for key in ("total_cost_usd", "cost_usd"):
                value = source.get(key)
                if isinstance(value, int | float):
                    return float(value)
        return None
