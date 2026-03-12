from __future__ import annotations

import json
from time import perf_counter
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy
from pydantic import BaseModel, Field

from app.agent.prompt_loader import PromptLoader
from app.cognition.types import (
    AgentActionInvocation,
    AgentDecisionResult,
    BackendExecutionContext,
    PlanningInvocation,
    ReflectionInvocation,
)
from app.infra.logging import get_logger
from app.infra.settings import Settings, get_settings

logger = get_logger(__name__)


class _StructuredDecision(BaseModel):
    action_type: str
    target_location_id: str | None = None
    target_agent_id: str | None = None
    message: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class _DecisionState(TypedDict):
    invocation: AgentActionInvocation
    result: AgentDecisionResult | None
    use_model: bool


class _DecisionContext(TypedDict):
    runtime_ctx: BackendExecutionContext | None


class LangGraphAgentBackend:
    """Minimal LangGraph-backed reactor stub.

    This first version only supports decide_action(). It keeps planner and
    reflector disabled so the backend can be integrated incrementally.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        decision_model: Any | None = None,
        text_model: Any | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        default_model = self._build_default_model()
        self._decision_model = decision_model or default_model
        self._text_model = text_model or decision_model or default_model
        graph = StateGraph(_DecisionState, context_schema=_DecisionContext)
        graph.add_node(
            "model_decide",
            self._model_decide_node,
            retry_policy=self._build_model_retry_policy(),
        )
        graph.add_node("fallback_decide", self._fallback_decide_node)
        graph.add_conditional_edges(
            START,
            self._route_start,
            {
                "model_decide": "model_decide",
                "fallback_decide": "fallback_decide",
            },
        )
        graph.add_edge("model_decide", END)
        graph.add_edge("fallback_decide", END)
        self._graph = graph.compile()

    async def decide_action(
        self,
        invocation: AgentActionInvocation,
        runtime_ctx: BackendExecutionContext | None = None,
    ) -> AgentDecisionResult:
        try:
            state = await self._graph.ainvoke(
                {
                    "invocation": invocation,
                    "result": None,
                    "use_model": self._decision_model is not None,
                },
                context={"runtime_ctx": runtime_ctx},
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"LangGraph reactor decision failed for {invocation.agent_id}: {exc}")
            return self._heuristic_decision(invocation)
        return state["result"] or AgentDecisionResult(action_type="rest")

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

    def _route_start(self, state: _DecisionState) -> str:
        return "model_decide" if state["use_model"] else "fallback_decide"

    async def _model_decide_node(
        self,
        state: _DecisionState,
        runtime: Any,
    ) -> _DecisionState:
        invocation = state["invocation"]
        runtime_ctx = runtime.context.get("runtime_ctx")
        result = await self._run_structured_reactor_decision(invocation, runtime_ctx)
        if result is not None:
            return {"invocation": invocation, "result": result, "use_model": True}

        result = await self._run_text_reactor_decision(invocation, runtime_ctx)
        if result is not None:
            return {"invocation": invocation, "result": result, "use_model": True}

        return {
            "invocation": invocation,
            "result": self._heuristic_decision(invocation),
            "use_model": True,
        }

    def _fallback_decide_node(self, state: _DecisionState) -> _DecisionState:
        invocation = state["invocation"]
        return {
            "invocation": invocation,
            "result": self._heuristic_decision(invocation),
            "use_model": False,
        }

    def _heuristic_decision(self, invocation: AgentActionInvocation) -> AgentDecisionResult:
        world = invocation.context.get("world", {})
        goal = world.get("current_goal")
        known_location_ids = world.get("known_location_ids")

        if isinstance(goal, str) and goal.startswith("move:"):
            target_location_id = goal.split(":", 1)[1].strip()
            if (
                isinstance(known_location_ids, list)
                and target_location_id not in known_location_ids
            ):
                return AgentDecisionResult(action_type="rest")
            return AgentDecisionResult(
                action_type="move",
                target_location_id=target_location_id,
            )

        return AgentDecisionResult(action_type="rest")

    def _build_default_model(self) -> Any | None:
        if not self._settings.langgraph_model or not self._settings.langgraph_api_key:
            return None

        from langchain_anthropic import ChatAnthropic

        model_kwargs: dict[str, Any] = {
            "model": self._settings.langgraph_model,
            "api_key": self._settings.langgraph_api_key,
            "temperature": 0,
        }
        if self._settings.langgraph_base_url:
            model_kwargs["base_url"] = self._settings.langgraph_base_url
        return ChatAnthropic(**model_kwargs)

    async def _run_text_task(
        self,
        *,
        agent_id: str,
        task: str,
        prompt: str,
        runtime_ctx: BackendExecutionContext | None,
    ) -> dict[str, Any] | None:
        if self._text_model is None:
            return None
        try:
            started_at = perf_counter()
            response = await self._text_model.ainvoke(
                f"{prompt}\n\n重要：只返回 JSON，不要有任何其他文字。"
            )
            duration_ms = int((perf_counter() - started_at) * 1000)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"LangGraph {task} failed for {agent_id}: {exc}")
            return None

        self._maybe_record_usage(runtime_ctx, agent_id, task, response, duration_ms)
        content = self._extract_text_content(response)
        if not content:
            return None
        parsed = PromptLoader.extract_json_from_text(content)
        if parsed is None:
            logger.warning(f"LangGraph {task} returned non-JSON for {agent_id}: {content[:200]}")
        return parsed

    def _build_model_retry_policy(self) -> RetryPolicy:
        return RetryPolicy(
            max_attempts=2,
            retry_on=lambda exc: isinstance(exc, RuntimeError),
        )

    def _build_model_prompt(self, invocation: AgentActionInvocation) -> str:
        context_json = json.dumps(invocation.context, ensure_ascii=False, sort_keys=True)
        allowed_actions = ", ".join(invocation.allowed_actions)
        return (
            f"{invocation.prompt}\n\n"
            f"Allowed actions: {allowed_actions}\n"
            f"Agent context JSON:\n{context_json}\n\n"
            "Return only the structured action decision."
        )

    async def _run_structured_reactor_decision(
        self,
        invocation: AgentActionInvocation,
        runtime_ctx: BackendExecutionContext | None,
    ) -> AgentDecisionResult | None:
        structured_model = self._build_structured_decision_model()
        started_at = perf_counter()
        try:
            response = await structured_model.ainvoke(self._build_model_prompt(invocation))
        except RuntimeError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                f"LangGraph structured reactor decision failed for {invocation.agent_id}: {exc}"
            )
            return None

        duration_ms = int((perf_counter() - started_at) * 1000)
        raw_response = response.get("raw") if self._is_structured_wrapper(response) else response
        self._maybe_record_usage(runtime_ctx, invocation.agent_id, "reactor", raw_response, duration_ms)

        parsed = self._extract_structured_response(response)
        if parsed is None:
            return None
        return self._coerce_model_result(parsed, invocation.allowed_actions)

    async def _run_text_reactor_decision(
        self,
        invocation: AgentActionInvocation,
        runtime_ctx: BackendExecutionContext | None,
    ) -> AgentDecisionResult | None:
        started_at = perf_counter()
        try:
            response = await self._decision_model.ainvoke(self._build_text_json_prompt(invocation))
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"LangGraph text reactor decision failed for {invocation.agent_id}: {exc}")
            return None

        duration_ms = int((perf_counter() - started_at) * 1000)
        self._maybe_record_usage(runtime_ctx, invocation.agent_id, "reactor", response, duration_ms)
        content = self._extract_text_content(response)
        if not content:
            return None
        parsed = PromptLoader.extract_json_from_text(content)
        if not isinstance(parsed, dict):
            return None
        return self._coerce_model_result(parsed, invocation.allowed_actions)

    def _build_text_json_prompt(self, invocation: AgentActionInvocation) -> str:
        schema_json = json.dumps(_StructuredDecision.model_json_schema(), ensure_ascii=False, indent=2)
        return (
            f"{self._build_model_prompt(invocation)}\n\n"
            "If native structured output is unavailable, return exactly one JSON object "
            "matching this schema and no additional text.\n"
            f"{schema_json}"
        )

    def _build_structured_decision_model(self) -> Any:
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

    def _maybe_record_usage(
        self,
        runtime_ctx: BackendExecutionContext | None,
        agent_id: str,
        task_type: str,
        response: Any,
        duration_ms: int,
    ) -> None:
        if runtime_ctx is None or runtime_ctx.on_llm_call is None:
            return
        if response is None:
            return
        usage = getattr(response, "usage_metadata", None)
        if usage is None and isinstance(response, dict):
            usage = response.get("usage_metadata")
        if usage is None:
            return
        runtime_ctx.on_llm_call(
            agent_id=agent_id,
            task_type=task_type,
            usage=usage,
            total_cost_usd=0.0,
            duration_ms=duration_ms,
        )
