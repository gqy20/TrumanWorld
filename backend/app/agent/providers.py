from __future__ import annotations

import asyncio
import json
import re
import shutil
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query
from claude_agent_sdk.types import McpSdkServerConfig
from pydantic import BaseModel, Field, ValidationError

from app.agent.system_prompt import build_system_prompt
from app.infra.logging import get_logger
from app.infra.settings import Settings

if TYPE_CHECKING:
    from app.agent.connection_pool import AgentConnectionPool
    from app.agent.runtime import RuntimeContext, RuntimeInvocation
    from app.sim.types import RuntimeWorldContext

logger = get_logger(__name__)


DECISION_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "action_type": {
            "type": "string",
            "enum": ["move", "talk", "work", "rest"],
        },
        "target_location_id": {"type": ["string", "null"]},
        "target_agent_id": {"type": ["string", "null"]},
        "message": {"type": ["string", "null"], "description": "对话消息内容（仅 talk 类型需要)"},
        "payload": {"type": "object"},
    },
    "required": ["action_type"],
    "additionalProperties": False,
}


class RuntimeDecision(BaseModel):
    action_type: str
    target_location_id: str | None = None
    target_agent_id: str | None = None
    message: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class AgentDecisionProvider(ABC):
    @abstractmethod
    async def decide(
        self,
        invocation: Any,
        runtime_ctx: "RuntimeContext | None" = None,
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
        runtime_ctx: "RuntimeContext | None" = None,
    ) -> RuntimeDecision:
        world = invocation.context.get("world", {})
        goal = world.get("current_goal")
        known_location_ids = world.get("known_location_ids")

        # move:xxx is a direct system instruction, not a behavior decision
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

        # All other goals: rest as safe fallback (LLM should handle these)
        return RuntimeDecision(action_type="rest")


class ClaudeSDKDecisionProvider(AgentDecisionProvider):
    """Claude SDK 决策提供者，支持连接池复用和 MCP memory tools。"""

    def __init__(
        self,
        settings: Settings,
        connection_pool: AgentConnectionPool | None = None,
    ) -> None:
        self.settings = settings
        self._pool = connection_pool

    @staticmethod
    def _get_pool_key(invocation: "RuntimeInvocation") -> str:
        """Generate pool key for connection isolation between runs.

        Args:
            invocation: Runtime invocation with agent_id and optional run_id.

        Returns:
            Pool key in format "run_id:agent_id" or just "agent_id" if no run_id.
        """
        if invocation.run_id:
            return f"{invocation.run_id}:{invocation.agent_id}"
        return invocation.agent_id

    def _build_sdk_options(
        self,
        invocation: RuntimeInvocation,
        runtime_ctx: "RuntimeContext | None" = None,
    ) -> ClaudeAgentOptions:
        """Build SDK options for a single invocation."""
        env = {}
        if self.settings.anthropic_api_key:
            env["ANTHROPIC_API_KEY"] = self.settings.anthropic_api_key
        if self.settings.anthropic_base_url:
            env["ANTHROPIC_BASE_URL"] = self.settings.anthropic_base_url

        # Note: output_format is not supported by MiniMax API
        budget = (
            invocation.max_budget_usd
            if invocation.max_budget_usd >= 0.1
            else self.settings.agent_budget_usd
        )

        # 确定 session_id：优先使用 invocation 中的，否则从连接池获取
        session_id = invocation.session_id
        pool_key = self._get_pool_key(invocation)
        if not session_id and self._pool:
            session_id = self._pool.get_session_id(pool_key)
            if session_id:
                logger.debug(f"Auto-resuming session {session_id} for pool_key: {pool_key}")

        options = ClaudeAgentOptions(
            max_turns=invocation.max_turns,
            max_budget_usd=budget,
            model=self.settings.agent_model,
            cwd=str(self.settings.project_root),
            env=env,
            system_prompt=build_system_prompt(),
            resume=session_id,  # 恢复之前的 session
        )

        # Add MCP memory server if enabled
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
        runtime_ctx: "RuntimeContext | None" = None,
    ) -> RuntimeDecision:
        """Make a decision using Claude SDK.

        支持两种模式:
        1. 连接池模式: 复用已建立的客户端连接，自动恢复 session
        2. 直接模式: 每次调用 query() 新建进程，使用 resume 参数恢复
        """
        pool_key = self._get_pool_key(invocation)
        if self._pool and self._pool.is_warmed_up(pool_key):
            logger.debug(f"Using POOLED connection for pool_key: {pool_key}")
            return await self._decide_with_pool(invocation, runtime_ctx=runtime_ctx)
        else:
            logger.debug(f"Using QUERY mode (new process) for pool_key: {pool_key}")
            return await self._decide_with_query(invocation, runtime_ctx=runtime_ctx)

    async def _decide_with_pool(
        self,
        invocation: RuntimeInvocation,
        runtime_ctx: "RuntimeContext | None" = None,
    ) -> RuntimeDecision:
        """使用连接池的客户端进行决策"""
        from claude_agent_sdk import AssistantMessage

        result_decision: RuntimeDecision | None = None
        captured_session_id: str | None = None
        pool_key = self._get_pool_key(invocation)

        # Acquire client from pool
        client = await self._pool.acquire(pool_key)

        try:
            # Send query
            json_schema = json.dumps(DECISION_OUTPUT_SCHEMA, indent=2)
            full_prompt = f"""{invocation.prompt}

重要：你必须只返回一个有效的 JSON 对象，不要有其他任何文本。JSON 格式如下:
{json_schema}

    返回 JSON，不要有 markdown 代码块标记。 """

            await client.query(full_prompt)

            # Receive response
            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if hasattr(block, "text") and block.text:
                            text = block.text.strip()
                            # Remove markdown code block markers
                            if text.startswith("```"):
                                text = re.sub(r"^```json?\n?", "", text)
                                text = re.sub(r"\n?```$", "", text)
                            text = text.strip()

                            # Try to parse JSON
                            try:
                                result_decision = RuntimeDecision.model_validate_json(text)
                            except Exception:
                                # Fallback: extract first { to last } pair
                                start = text.find("{")
                                end = text.rfind("}")
                                if start != -1 and end != -1 and end > start:
                                    json_str = text[start : end + 1]
                                    result_decision = RuntimeDecision.model_validate_json(json_str)
                                else:
                                    raise ValueError("No valid JSON found in response")
                elif isinstance(message, ResultMessage):
                    captured_session_id = message.session_id  # 捕获 session_id
                    if message.is_error:
                        msg = message.result or "Claude SDK decision failed"
                        raise RuntimeError(msg)
                    # 记录 token 消耗
                    if runtime_ctx and runtime_ctx.on_llm_call:
                        runtime_ctx.on_llm_call(
                            agent_id=invocation.agent_id,
                            task_type=invocation.task,
                            usage=message.usage,
                            total_cost_usd=message.total_cost_usd,
                            duration_ms=message.duration_ms,
                        )

            if result_decision is None:
                msg = "Claude SDK returned no decision"
                raise RuntimeError(msg)

            return result_decision

        finally:
            # 释放连接并保存 session_id
            await self._pool.release(
                pool_key,
                session_id=captured_session_id,
            )

    async def _decide_with_query(
        self,
        invocation: RuntimeInvocation,
        runtime_ctx: "RuntimeContext | None" = None,
    ) -> RuntimeDecision:
        """使用 query() 进行决策（原有逻辑)

        支持 resume 参数恢复历史对话。
        """
        if shutil.which("claude") is None:
            msg = "Claude CLI is not available in the current environment"
            raise RuntimeError(msg)

        options = self._build_sdk_options(invocation, runtime_ctx=runtime_ctx)

        # 日志记录 resume 状态
        if invocation.session_id:
            logger.debug(
                f"Resuming session {invocation.session_id} for agent {invocation.agent_id}"
            )

        # Build prompt that asks for JSON response
        json_schema = json.dumps(DECISION_OUTPUT_SCHEMA, indent=2)
        full_prompt = f"""{invocation.prompt}

重要:你必须只返回一个有效的 JSON 对象，不要有其他任何文本。JSON 格式如下:
{json_schema}

    返回 JSON，不要有 markdown 代码块标记. """

        try:
            return await self._query_internal(invocation, full_prompt, options, runtime_ctx)
        except asyncio.CancelledError:
            # 任务被取消，这是正常的(如 scheduler 停止时),不需要抛出异常
            logger.debug(f"Claude SDK decision cancelled for agent {invocation.agent_id}")
            return RuntimeDecision(action_type="rest")
        except RuntimeError as e:
            # Handle claude_agent_sdk anyio cancel scope errors
            if "cancel scope" in str(e).lower() or "different task" in str(e).lower():
                logger.debug(f"Claude SDK cancel scope error for agent {invocation.agent_id}: {e}")
                return RuntimeDecision(action_type="rest")
            raise

    async def _query_internal(
        self,
        invocation: RuntimeInvocation,
        full_prompt: str,
        options: "ClaudeAgentOptions",
        runtime_ctx: "RuntimeContext | None" = None,
    ) -> RuntimeDecision:
        """Internal query execution - separated to handle SDK cleanup issues."""
        result_decision: RuntimeDecision | None = None
        captured_session_id: str | None = None
        gen = None

        try:
            gen = query(prompt=full_prompt, options=options)
            async for message in gen:
                if isinstance(message, ResultMessage):
                    captured_session_id = message.session_id  # 捕获 session_id
                    if message.is_error:
                        msg = message.result or "Claude SDK decision failed"
                        raise RuntimeError(msg)
                    # 记录 token 消耗
                    if runtime_ctx and runtime_ctx.on_llm_call:
                        runtime_ctx.on_llm_call(
                            agent_id=invocation.agent_id,
                            task_type=invocation.task,
                            usage=message.usage,
                            total_cost_usd=message.total_cost_usd,
                            duration_ms=message.duration_ms,
                        )
                    # Parse JSON from text response
                    if message.result:
                        text = message.result.strip()
                        # Remove markdown code block markers if present
                        if text.startswith("```"):
                            text = re.sub(r"^```json?\n?", "", text)
                            text = re.sub(r"\n?```$", "", text)
                        text = text.strip()
                        # Try to parse as-is first
                        try:
                            result_decision = RuntimeDecision.model_validate_json(text)
                        except Exception:
                            # Fallback: extract first { to last } pair
                            start = text.find("{")
                            end = text.rfind("}")
                            if start != -1 and end != -1 and end > start:
                                json_str = text[start : end + 1]
                                result_decision = RuntimeDecision.model_validate_json(json_str)
                            else:
                                raise ValueError("No valid JSON found in response")
                        except (json.JSONDecodeError, ValidationError) as exc:
                            msg = f"Failed to parse decision JSON: {exc}"
                            raise RuntimeError(msg) from exc
        finally:
            # Properly close the async generator
            if gen is not None:
                try:
                    await gen.aclose()
                except RuntimeError:
                    # Ignore "cancel scope in different task" errors - this is a known SDK issue
                    pass

        if result_decision is None:
            msg = "Claude SDK returned no decision"
            raise RuntimeError(msg)

        # 记录 session_id 用于追踪
        if captured_session_id:
            logger.debug(
                f"Agent {invocation.agent_id} session_id={captured_session_id} "
                f"(resume={invocation.session_id is not None})"
            )

        return result_decision
