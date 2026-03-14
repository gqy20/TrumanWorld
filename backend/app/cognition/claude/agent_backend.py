from __future__ import annotations

import shutil
from dataclasses import dataclass
from typing import Any

from app.agent.prompt_loader import PromptLoader
from app.cognition.claude.connection_pool import AgentConnectionPool
from app.cognition.claude.decision_provider import ClaudeSDKDecisionProvider
from app.cognition.claude.decision_utils import clean_response_text
from app.cognition.claude.free_text_utils import run_text_query
from app.cognition.types import (
    AgentActionInvocation,
    AgentDecisionResult,
    BackendExecutionContext,
    PlanningInvocation,
    ReflectionInvocation,
)
from app.infra.logging import get_logger
from app.infra.settings import Settings

logger = get_logger(__name__)


@dataclass
class _RuntimeContextAdapter:
    run_id: str | None = None
    enable_memory_tools: bool = True
    on_llm_call: Any | None = None
    memory_cache: Any | None = None


class _RuntimeInvocationAdapter:
    def __init__(
        self,
        invocation: AgentActionInvocation,
        run_id: str | None,
    ) -> None:
        self.agent_id = invocation.agent_id
        self.task = "reactor"
        self.prompt = invocation.prompt
        self.context = invocation.context
        self.max_turns = invocation.max_turns
        self.max_budget_usd = invocation.max_budget_usd
        self.allowed_actions = list(invocation.allowed_actions)
        self.run_id = run_id
        self.session_id = None


class ClaudeSdkAgentBackend:
    """Claude adapter.

    Reactor decisions may use a pooled ClaudeSDKClient when enabled.
    Planner and reflector must remain one-shot query() calls so they do not
    inherit long-lived client lifecycle and cross-task cancellation issues.
    """

    def __init__(
        self,
        settings: Settings,
        connection_pool: AgentConnectionPool | None = None,
    ) -> None:
        self._settings = settings
        self._provider = ClaudeSDKDecisionProvider(settings, connection_pool=connection_pool)

    @staticmethod
    def _to_runtime_context(
        runtime_ctx: BackendExecutionContext | None,
    ) -> _RuntimeContextAdapter | None:
        if runtime_ctx is None:
            return None
        return _RuntimeContextAdapter(
            run_id=runtime_ctx.run_id,
            enable_memory_tools=runtime_ctx.enable_memory_tools,
            on_llm_call=runtime_ctx.on_llm_call,
            memory_cache=runtime_ctx.memory_cache,
        )

    async def decide_action(
        self,
        invocation: AgentActionInvocation,
        runtime_ctx: BackendExecutionContext | None = None,
    ) -> AgentDecisionResult:
        runtime_invocation = _RuntimeInvocationAdapter(
            invocation,
            run_id=runtime_ctx.run_id if runtime_ctx else None,
        )
        decision = await self._provider.decide(
            runtime_invocation,
            runtime_ctx=self._to_runtime_context(runtime_ctx),
        )
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
        # Intentionally bypass the pooled client path. Planning is low-frequency
        # and should stay stateless even if a reactor pool is configured.
        return await self._run_free_text_llm(
            agent_id=invocation.agent_id,
            task="planner",
            prompt=invocation.prompt,
            runtime_ctx=runtime_ctx,
        )

    async def reflect_day(
        self,
        invocation: ReflectionInvocation,
        runtime_ctx: BackendExecutionContext | None = None,
    ) -> dict[str, Any] | None:
        # Intentionally bypass the pooled client path. Reflection is a one-shot
        # daily task and should not reuse long-lived ClaudeSDKClient sessions.
        return await self._run_free_text_llm(
            agent_id=invocation.agent_id,
            task="reflector",
            prompt=invocation.prompt,
            runtime_ctx=runtime_ctx,
        )

    async def _run_free_text_llm(
        self,
        agent_id: str,
        task: str,
        prompt: str,
        runtime_ctx: BackendExecutionContext | None = None,
    ) -> dict[str, Any] | None:
        # Do not route planner/reflector through ClaudeSDKDecisionProvider or the
        # reactor connection pool. These tasks are intentionally modeled as
        # one-shot query() calls.
        if shutil.which("claude") is None:
            logger.warning(f"Skipping {task} for {agent_id}: claude CLI not available")
            return None

        from app.agent.system_prompt import build_system_prompt
        from app.cognition.claude.sdk_options import build_sdk_options

        options = build_sdk_options(
            self._settings,
            max_turns=4,
            max_budget_usd=0.05,
            model=self._settings.agent_model,
            cwd=str(self._settings.project_root),
            system_prompt=build_system_prompt(),
        )

        full_prompt = f"{prompt}\n\n重要：只返回 JSON，不要有任何其他文字。"

        try:
            result_text = await run_text_query(
                prompt=full_prompt,
                options=options,
                on_usage=(
                    lambda usage, total_cost_usd, duration_ms: (
                        runtime_ctx.on_llm_call(
                            agent_id=agent_id,
                            task_type=task,
                            usage=usage,
                            total_cost_usd=total_cost_usd,
                            duration_ms=duration_ms,
                        )
                        if runtime_ctx and runtime_ctx.on_llm_call
                        else None
                    )
                ),
            )
        except RuntimeError as exc:
            logger.warning(f"{task} LLM error for {agent_id}: {exc}")
            return None
        except Exception as exc:
            logger.warning(f"{task} LLM call failed for {agent_id}: {exc}")
            return None

        if not result_text:
            return None

        parsed = PromptLoader.extract_json_from_text(clean_response_text(result_text))
        if parsed is None:
            logger.warning(f"{task} could not parse JSON for {agent_id}: {result_text[:200]}")
        return parsed
