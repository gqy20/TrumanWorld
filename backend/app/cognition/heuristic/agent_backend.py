from __future__ import annotations

from typing import Any

from app.cognition.claude.decision_provider import HeuristicDecisionHook, HeuristicDecisionProvider
from app.cognition.types import (
    AgentActionInvocation,
    AgentDecisionResult,
    BackendExecutionContext,
    PlanningInvocation,
    ReflectionInvocation,
)


class _InvocationAdapter:
    def __init__(self, invocation: AgentActionInvocation, run_id: str | None) -> None:
        self.agent_id = invocation.agent_id
        self.prompt = invocation.prompt
        self.context = invocation.context
        self.max_turns = invocation.max_turns
        self.max_budget_usd = invocation.max_budget_usd
        self.allowed_actions = invocation.allowed_actions
        self.run_id = run_id
        self.session_id = None
        self.task = "reactor"


class HeuristicAgentBackend:
    def __init__(self, provider: HeuristicDecisionProvider | None = None) -> None:
        self._provider = provider or HeuristicDecisionProvider()

    def set_decision_hook(self, decision_hook: HeuristicDecisionHook | None) -> None:
        if hasattr(self._provider, "set_decision_hook"):
            self._provider.set_decision_hook(decision_hook)

    async def decide_action(
        self,
        invocation: AgentActionInvocation,
        runtime_ctx: BackendExecutionContext | None = None,
    ) -> AgentDecisionResult:
        adapted = _InvocationAdapter(invocation, runtime_ctx.run_id if runtime_ctx else None)
        decision = await self._provider.decide(adapted, runtime_ctx=runtime_ctx)
        return AgentDecisionResult(
            action_type=decision.action_type,
            target_location_id=decision.target_location_id,
            target_agent_id=decision.target_agent_id,
            message=decision.message,
            payload=dict(decision.payload),
        )

    async def plan_day(
        self,
        invocation: PlanningInvocation,
        runtime_ctx: BackendExecutionContext | None = None,
    ) -> dict[str, Any] | None:
        return None

    async def reflect_day(
        self,
        invocation: ReflectionInvocation,
        runtime_ctx: BackendExecutionContext | None = None,
    ) -> dict[str, Any] | None:
        return None
