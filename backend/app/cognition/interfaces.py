from __future__ import annotations

from typing import Any, Protocol

from app.cognition.types import (
    AgentActionInvocation,
    AgentDecisionResult,
    BackendExecutionContext,
    DirectorDecisionInvocation,
    PlanningInvocation,
    ReflectionInvocation,
)


class AgentCognitionBackend(Protocol):
    async def decide_action(
        self,
        invocation: AgentActionInvocation,
        runtime_ctx: BackendExecutionContext | None = None,
    ) -> AgentDecisionResult: ...

    async def plan_day(
        self,
        invocation: PlanningInvocation,
        runtime_ctx: BackendExecutionContext | None = None,
    ) -> dict[str, Any] | None: ...

    async def reflect_day(
        self,
        invocation: ReflectionInvocation,
        runtime_ctx: BackendExecutionContext | None = None,
    ) -> dict[str, Any] | None: ...


class DirectorCognitionBackend(Protocol):
    def is_enabled(self) -> bool: ...

    def should_decide(self, tick_no: int) -> bool: ...

    async def propose_intervention(
        self,
        invocation: DirectorDecisionInvocation,
    ) -> Any | None: ...
