from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.cognition.types import (
    AgentActionInvocation,
    AgentDecisionResult,
    BackendExecutionContext,
    PlanningInvocation,
    ReflectionInvocation,
)


class _DecisionState(TypedDict):
    invocation: AgentActionInvocation
    result: AgentDecisionResult | None


class LangGraphAgentBackend:
    """Minimal LangGraph-backed reactor stub.

    This first version only supports decide_action(). It keeps planner and
    reflector disabled so the backend can be integrated incrementally.
    """

    def __init__(self) -> None:
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
        state = await self._graph.ainvoke({"invocation": invocation, "result": None})
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

    def _decide_node(self, state: _DecisionState) -> _DecisionState:
        invocation = state["invocation"]
        world = invocation.context.get("world", {})
        goal = world.get("current_goal")
        known_location_ids = world.get("known_location_ids")

        if isinstance(goal, str) and goal.startswith("move:"):
            target_location_id = goal.split(":", 1)[1].strip()
            if (
                isinstance(known_location_ids, list)
                and target_location_id not in known_location_ids
            ):
                return {"invocation": invocation, "result": AgentDecisionResult(action_type="rest")}
            return {
                "invocation": invocation,
                "result": AgentDecisionResult(
                    action_type="move",
                    target_location_id=target_location_id,
                ),
            }

        return {"invocation": invocation, "result": AgentDecisionResult(action_type="rest")}
