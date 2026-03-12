from __future__ import annotations

import json
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

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
    runtime_ctx: BackendExecutionContext | None
    result: AgentDecisionResult | None


class LangGraphAgentBackend:
    """Minimal LangGraph-backed reactor stub.

    This first version only supports decide_action(). It keeps planner and
    reflector disabled so the backend can be integrated incrementally.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        decision_model: Any | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._decision_model = decision_model or self._build_default_model()
        graph = StateGraph(_DecisionState)
        graph.add_node("decide", self._decide_node)
        graph.add_edge(START, "decide")
        graph.add_edge("decide", END)
        self._graph = graph.compile()

    async def decide_action(
        self,
        invocation: AgentActionInvocation,
        runtime_ctx: BackendExecutionContext | None = None,
    ) -> AgentDecisionResult:
        state = await self._graph.ainvoke(
            {"invocation": invocation, "runtime_ctx": runtime_ctx, "result": None}
        )
        return state["result"] or AgentDecisionResult(action_type="rest")

    async def plan_day(
        self,
        invocation: PlanningInvocation,
        runtime_ctx: BackendExecutionContext | None = None,
    ) -> dict | None:
        return None

    async def reflect_day(
        self,
        invocation: ReflectionInvocation,
        runtime_ctx: BackendExecutionContext | None = None,
    ) -> dict | None:
        return None

    async def _decide_node(self, state: _DecisionState) -> _DecisionState:
        invocation = state["invocation"]
        runtime_ctx = state["runtime_ctx"]

        heuristic_result = self._heuristic_decision(invocation)
        if self._decision_model is None:
            return {"invocation": invocation, "runtime_ctx": runtime_ctx, "result": heuristic_result}

        try:
            structured_model = self._decision_model.with_structured_output(_StructuredDecision)
            response = await structured_model.ainvoke(self._build_model_prompt(invocation))
            result = self._coerce_model_result(response, invocation.allowed_actions)
            if result is not None:
                self._maybe_record_usage(runtime_ctx, invocation, response)
                return {"invocation": invocation, "runtime_ctx": runtime_ctx, "result": result}
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"LangGraph reactor decision failed for {invocation.agent_id}: {exc}")

        return {"invocation": invocation, "runtime_ctx": runtime_ctx, "result": heuristic_result}

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
        if not self._settings.agent_model or not self._settings.anthropic_api_key:
            return None

        from langchain_anthropic import ChatAnthropic

        model_kwargs: dict[str, Any] = {
            "model": self._settings.agent_model,
            "api_key": self._settings.anthropic_api_key,
            "temperature": 0,
        }
        if self._settings.anthropic_base_url:
            model_kwargs["base_url"] = self._settings.anthropic_base_url
        return ChatAnthropic(**model_kwargs)

    def _build_model_prompt(self, invocation: AgentActionInvocation) -> str:
        context_json = json.dumps(invocation.context, ensure_ascii=False, sort_keys=True)
        allowed_actions = ", ".join(invocation.allowed_actions)
        return (
            f"{invocation.prompt}\n\n"
            f"Allowed actions: {allowed_actions}\n"
            f"Agent context JSON:\n{context_json}\n\n"
            "Return only the structured action decision."
        )

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
        return AgentDecisionResult(
            action_type=action_type,
            target_location_id=data.get("target_location_id"),
            target_agent_id=data.get("target_agent_id"),
            message=data.get("message"),
            payload=dict(data.get("payload") or {}),
        )

    def _maybe_record_usage(
        self,
        runtime_ctx: BackendExecutionContext | None,
        invocation: AgentActionInvocation,
        response: Any,
    ) -> None:
        if runtime_ctx is None or runtime_ctx.on_llm_call is None:
            return
        usage = getattr(response, "usage_metadata", None)
        if usage is None and isinstance(response, dict):
            usage = response.get("usage_metadata")
        if usage is None:
            return
        runtime_ctx.on_llm_call(
            agent_id=invocation.agent_id,
            task_type="reactor",
            usage=usage,
            total_cost_usd=0.0,
            duration_ms=0,
        )
