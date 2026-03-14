from __future__ import annotations

import asyncio
import shutil
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query
from claude_agent_sdk.types import McpSdkServerConfig

from app.agent.system_prompt import build_system_prompt
from app.cognition.claude.decision_utils import (
    RuntimeDecision,
    build_decision_prompt,
    parse_runtime_decision,
)
from app.cognition.claude.sdk_options import build_sdk_options
from app.infra.logging import get_logger
from app.infra.settings import Settings

if TYPE_CHECKING:
    from app.agent.runtime import RuntimeContext, RuntimeInvocation
    from app.cognition.claude.connection_pool import AgentConnectionPool
    from app.sim.types import RuntimeWorldContext

logger = get_logger(__name__)


class AgentDecisionProvider(ABC):
    @abstractmethod
    async def decide(
        self,
        invocation: Any,
        runtime_ctx: RuntimeContext | None = None,
    ) -> RuntimeDecision:
        raise NotImplementedError


DEFAULT_TALK_MESSAGE = ""


def build_default_talk_message() -> str:
    """Deprecated: returns empty string. LLM must provide message content."""
    return DEFAULT_TALK_MESSAGE


HeuristicDecisionHook = Callable[
    ["RuntimeWorldContext", str | None, str | None, str | None, str | None],
    RuntimeDecision | None,
]


class HeuristicDecisionProvider(AgentDecisionProvider):
    """Minimal fallback decision provider.

    Only handles the move:xxx direct instruction format.
    All other behavior is delegated to LLM.
    """

    def __init__(self, decision_hook: HeuristicDecisionHook | None = None) -> None:
        self._decision_hook = decision_hook

    def set_decision_hook(self, decision_hook: HeuristicDecisionHook | None) -> None:
        self._decision_hook = decision_hook

    async def decide(
        self,
        invocation: Any,
        runtime_ctx: RuntimeContext | None = None,
    ) -> RuntimeDecision:
        world = invocation.context.get("world", {})
        goal = world.get("current_goal")
        known_location_ids = world.get("known_location_ids")

        if isinstance(goal, str) and goal.startswith("move:"):
            target_location_id = goal.split(":", 1)[1].strip()
            if (
                isinstance(known_location_ids, list)
                and target_location_id not in known_location_ids
            ):
                return RuntimeDecision(action_type="rest")
            return RuntimeDecision(
                action_type="move",
                target_location_id=target_location_id,
            )

        if self._decision_hook is not None:
            agent_id = getattr(invocation, "agent_id", None)
            nearby_agent_id = world.get("nearby_agent_id")
            current_location_id = world.get("current_location_id")
            home_location_id = world.get("home_location_id")
            hook_decision = self._decision_hook(
                world=world,
                nearby_agent_id=nearby_agent_id,
                current_location_id=current_location_id,
                home_location_id=home_location_id,
                agent_id=agent_id,
            )
            if hook_decision is not None:
                return hook_decision

        return RuntimeDecision(action_type="rest")


class ClaudeSDKDecisionProvider(AgentDecisionProvider):
    """Claude SDK decision provider with optional pooled reactor clients."""

    max_retries: int = 2

    def __init__(
        self,
        settings: Settings,
        connection_pool: AgentConnectionPool | None = None,
    ) -> None:
        self.settings = settings
        self._pool = connection_pool

    @staticmethod
    def _get_pool_key(invocation: RuntimeInvocation) -> str:
        if invocation.run_id:
            return f"{invocation.run_id}:{invocation.agent_id}"
        return invocation.agent_id

    def _build_sdk_options(
        self,
        invocation: RuntimeInvocation,
        runtime_ctx: RuntimeContext | None = None,
    ) -> ClaudeAgentOptions:
        budget = (
            invocation.max_budget_usd
            if invocation.max_budget_usd >= 0.1
            else self.settings.agent_budget_usd
        )

        session_id = invocation.session_id
        pool_key = self._get_pool_key(invocation)
        if not session_id and self._pool:
            session_id = self._pool.get_session_id(pool_key)
            if session_id:
                logger.debug(f"Auto-resuming session {session_id} for pool_key: {pool_key}")

        options = build_sdk_options(
            self.settings,
            max_turns=invocation.max_turns,
            max_budget_usd=budget,
            model=self.settings.agent_model,
            cwd=str(self.settings.project_root),
            system_prompt=build_system_prompt(),
            resume=session_id,
        )

        if runtime_ctx and runtime_ctx.enable_memory_tools and runtime_ctx.memory_cache is not None:
            from app.agent.memory_mcp_server_cached import create_memory_mcp_server_cached

            memory_server = create_memory_mcp_server_cached(runtime_ctx.memory_cache)
            options.mcp_servers = {
                "trumanworld-memory": McpSdkServerConfig(
                    type="sdk",
                    name="trumanworld-memory",
                    instance=memory_server,
                )
            }

        return options

    async def decide(
        self,
        invocation: RuntimeInvocation,
        runtime_ctx: RuntimeContext | None = None,
    ) -> RuntimeDecision:
        pool_key = self._get_pool_key(invocation)
        if self._pool and self._pool.is_warmed_up(pool_key):
            logger.debug(f"Using POOLED connection for pool_key: {pool_key}")
            return await self._decide_with_pool(invocation, runtime_ctx=runtime_ctx)

        logger.debug(f"Using QUERY mode (new process) for pool_key: {pool_key}")
        return await self._decide_with_query(invocation, runtime_ctx=runtime_ctx)

    async def _decide_with_pool(
        self,
        invocation: RuntimeInvocation,
        runtime_ctx: RuntimeContext | None = None,
    ) -> RuntimeDecision:
        max_attempts = self.max_retries + 1
        last_exc: Exception | None = None

        for attempt in range(max_attempts):
            try:
                return await self._decide_with_pool_once(invocation, runtime_ctx=runtime_ctx)
            except asyncio.CancelledError:
                logger.debug(f"Claude SDK pool decision cancelled for agent {invocation.agent_id}")
                return RuntimeDecision(action_type="rest")
            except RuntimeError as exc:
                if "cancel scope" in str(exc).lower() or "different task" in str(exc).lower():
                    logger.debug(
                        f"Claude SDK pool cancel scope error for agent {invocation.agent_id}: {exc}"
                    )
                    return RuntimeDecision(action_type="rest")
                last_exc = exc
                if attempt < max_attempts - 1:
                    logger.warning(
                        f"Claude SDK pool decision failed for agent {invocation.agent_id} "
                        f"(attempt {attempt + 1}/{max_attempts}): {exc}. Retrying..."
                    )
                else:
                    logger.warning(
                        f"Claude SDK pool decision exhausted all {max_attempts} attempts "
                        f"for agent {invocation.agent_id}: {exc}"
                    )
            except ValueError as exc:
                last_exc = exc
                if attempt < max_attempts - 1:
                    logger.warning(
                        f"Claude SDK pool JSON parse failed for agent {invocation.agent_id} "
                        f"(attempt {attempt + 1}/{max_attempts}): {exc}. Retrying..."
                    )
                else:
                    logger.warning(
                        f"Claude SDK pool JSON parse exhausted all {max_attempts} attempts "
                        f"for agent {invocation.agent_id}: {exc}"
                    )

        raise last_exc  # type: ignore[misc]

    async def _decide_with_pool_once(
        self,
        invocation: RuntimeInvocation,
        runtime_ctx: RuntimeContext | None = None,
    ) -> RuntimeDecision:
        from claude_agent_sdk import AssistantMessage

        result_decision: RuntimeDecision | None = None
        captured_session_id: str | None = None
        pool_key = self._get_pool_key(invocation)
        had_error = False

        client = await self._pool.acquire(pool_key)

        try:
            full_prompt = build_decision_prompt(invocation.prompt)
            await client.query(full_prompt)

            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if hasattr(block, "text") and block.text:
                            try:
                                result_decision = parse_runtime_decision(block.text)
                            except Exception:
                                raise ValueError("No valid JSON found in response")
                elif isinstance(message, ResultMessage):
                    captured_session_id = message.session_id
                    if message.is_error:
                        msg = message.result or "Claude SDK decision failed"
                        raise RuntimeError(msg)
                    if result_decision is None and message.result:
                        try:
                            result_decision = parse_runtime_decision(message.result)
                        except Exception:
                            pass
                    if runtime_ctx and runtime_ctx.on_llm_call:
                        runtime_ctx.on_llm_call(
                            agent_id=invocation.agent_id,
                            task_type=invocation.task,
                            usage=message.usage,
                            total_cost_usd=message.total_cost_usd,
                            duration_ms=message.duration_ms,
                        )

            if result_decision is None:
                had_error = True
                raise RuntimeError("Claude SDK returned no decision")

            return result_decision

        except Exception:
            had_error = True
            raise
        finally:
            await self._pool.release(
                pool_key,
                had_error=had_error,
                session_id=captured_session_id,
            )

    async def _decide_with_query(
        self,
        invocation: RuntimeInvocation,
        runtime_ctx: RuntimeContext | None = None,
    ) -> RuntimeDecision:
        if shutil.which("claude") is None:
            raise RuntimeError("Claude CLI is not available in the current environment")

        options = self._build_sdk_options(invocation, runtime_ctx=runtime_ctx)
        if invocation.session_id:
            logger.debug(
                f"Resuming session {invocation.session_id} for agent {invocation.agent_id}"
            )

        full_prompt = build_decision_prompt(invocation.prompt)
        max_attempts = self.max_retries + 1
        last_exc: Exception | None = None

        for attempt in range(max_attempts):
            try:
                return await self._query_internal(invocation, full_prompt, options, runtime_ctx)
            except asyncio.CancelledError:
                logger.debug(f"Claude SDK decision cancelled for agent {invocation.agent_id}")
                return RuntimeDecision(action_type="rest")
            except RuntimeError as exc:
                if "cancel scope" in str(exc).lower() or "different task" in str(exc).lower():
                    logger.debug(
                        f"Claude SDK cancel scope error for agent {invocation.agent_id}: {exc}"
                    )
                    return RuntimeDecision(action_type="rest")
                last_exc = exc
                if attempt < max_attempts - 1:
                    logger.warning(
                        f"Claude SDK decision failed for agent {invocation.agent_id} "
                        f"(attempt {attempt + 1}/{max_attempts}): {exc}. Retrying..."
                    )
                else:
                    logger.warning(
                        f"Claude SDK decision exhausted all {max_attempts} attempts "
                        f"for agent {invocation.agent_id}: {exc}"
                    )
            except ValueError as exc:
                last_exc = exc
                if attempt < max_attempts - 1:
                    logger.warning(
                        f"Claude SDK JSON parse failed for agent {invocation.agent_id} "
                        f"(attempt {attempt + 1}/{max_attempts}): {exc}. Retrying..."
                    )
                else:
                    logger.warning(
                        f"Claude SDK JSON parse exhausted all {max_attempts} attempts "
                        f"for agent {invocation.agent_id}: {exc}"
                    )

        raise last_exc  # type: ignore[misc]

    async def _query_internal(
        self,
        invocation: RuntimeInvocation,
        full_prompt: str,
        options: ClaudeAgentOptions,
        runtime_ctx: RuntimeContext | None = None,
    ) -> RuntimeDecision:
        result_decision: RuntimeDecision | None = None
        captured_session_id: str | None = None
        gen = None

        try:
            gen = query(prompt=full_prompt, options=options)
            async for message in gen:
                if isinstance(message, ResultMessage):
                    captured_session_id = message.session_id
                    if message.is_error:
                        raise RuntimeError(message.result or "Claude SDK decision failed")
                    if runtime_ctx and runtime_ctx.on_llm_call:
                        runtime_ctx.on_llm_call(
                            agent_id=invocation.agent_id,
                            task_type=invocation.task,
                            usage=message.usage,
                            total_cost_usd=message.total_cost_usd,
                            duration_ms=message.duration_ms,
                        )
                    if message.result:
                        try:
                            result_decision = parse_runtime_decision(message.result)
                        except ValueError:
                            raise
                        except RuntimeError:
                            raise
        finally:
            if gen is not None:
                try:
                    await gen.aclose()
                except RuntimeError:
                    pass

        if result_decision is None:
            raise RuntimeError("Claude SDK returned no decision")

        if captured_session_id:
            logger.debug(
                f"Agent {invocation.agent_id} session_id={captured_session_id} "
                f"(resume={invocation.session_id is not None})"
            )

        return result_decision
