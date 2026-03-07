from __future__ import annotations

from __future__ import annotations

import asyncio
import json
import logging
import re
import shutil
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query
from pydantic import BaseModel, Field, ValidationError

from app.infra.settings import Settings

if TYPE_CHECKING:
    from app.agent.connection_pool import AgentConnectionPool
    from app.agent.runtime import RuntimeInvocation

logger = logging.getLogger(__name__)


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
    async def decide(self, invocation: Any) -> RuntimeDecision:
        raise NotImplementedError


DEFAULT_TALK_MESSAGE = "你好，最近怎么样？"


def build_default_talk_message() -> str:
    return DEFAULT_TALK_MESSAGE


class HeuristicDecisionProvider(AgentDecisionProvider):
    # 简单的问候语列表，用于启发式对话
    TALK_MESSAGES = [
        "你好啊！最近怎么样？",
        "今天天气真不错！",
        "有什么新鲜事吗?",
        "好久不见！",
        "最近工作怎么样？",
        "一起喝杯咖啡吧?",
    ]

    async def decide(self, invocation: Any) -> RuntimeDecision:
        import random

        world = invocation.context.get("world", {})
        goal = world.get("current_goal")
        current_location_id = world.get("current_location_id")
        home_location_id = world.get("home_location_id")
        nearby_agent_id = world.get("nearby_agent_id")

        if isinstance(goal, str) and goal.startswith("move:"):
            return RuntimeDecision(
                action_type="move",
                target_location_id=goal.split(":", 1)[1].strip(),
            )

        if goal == "work":
            return RuntimeDecision(action_type="work")

        if goal == "talk" and nearby_agent_id:
            return RuntimeDecision(
                action_type="talk",
                target_agent_id=str(nearby_agent_id),
                message=random.choice(self.TALK_MESSAGES),
            )

        if (
            current_location_id
            and home_location_id
            and current_location_id != home_location_id
            and goal == "go_home"
        ):
            return RuntimeDecision(
                action_type="move",
                target_location_id=str(home_location_id),
            )

        return RuntimeDecision(action_type="rest")


class ClaudeSDKDecisionProvider(AgentDecisionProvider):
    """Claude SDK 决策提供者，支持连接池复用。"""

    def __init__(
        self,
        settings: Settings,
        connection_pool: AgentConnectionPool | None = None,
    ) -> None:
        self.settings = settings
        self._pool = connection_pool

    def _build_sdk_options(self, invocation: RuntimeInvocation) -> ClaudeAgentOptions:
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
        return ClaudeAgentOptions(
            max_turns=invocation.max_turns,
            max_budget_usd=budget,
            model=self.settings.agent_model,
            cwd=str(self.settings.project_root),
            env=env,
        )

    async def decide(self, invocation: RuntimeInvocation) -> RuntimeDecision:
        """Make a decision using Claude SDK.

        支持两种模式:
        1. 连接池模式: 复用已建立的客户端连接
        2. 直接模式: 每次调用 query() 新建进程
        """
        if self._pool and self._pool.is_warmed_up(invocation.agent_id):
            return await self._decide_with_pool(invocation)
        else:
            return await self._decide_with_query(invocation)

    async def _decide_with_pool(self, invocation: RuntimeInvocation) -> RuntimeDecision:
        """使用连接池的客户端进行决策"""
        from claude_agent_sdk import AssistantMessage

        result_decision: RuntimeDecision | None = None

        # Acquire client from pool
        client = await self._pool.acquire(invocation.agent_id)

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
                    if message.is_error:
                        msg = message.result or "Claude SDK decision failed"
                        raise RuntimeError(msg)

            if result_decision is None:
                msg = "Claude SDK returned no decision"
                raise RuntimeError(msg)

            return result_decision

        finally:
            await self._pool.release(invocation.agent_id)

    async def _decide_with_query(self, invocation: RuntimeInvocation) -> RuntimeDecision:
        """使用 query() 进行决策（原有逻辑)"""
        result_decision: RuntimeDecision | None = None
        gen = None

        if shutil.which("claude") is None:
            msg = "Claude CLI is not available in the current environment"
            raise RuntimeError(msg)

        options = self._build_sdk_options(invocation)

        # Build prompt that asks for JSON response
        json_schema = json.dumps(DECISION_OUTPUT_SCHEMA, indent=2)
        full_prompt = f"""{invocation.prompt}

重要:你必须只返回一个有效的 JSON 对象，不要有其他任何文本。JSON 格式如下:
{json_schema}

    返回 JSON，不要有 markdown 代码块标记. """

        try:
            gen = query(prompt=full_prompt, options=options)
            async for message in gen:
                if isinstance(message, ResultMessage):
                    if message.is_error:
                        msg = message.result or "Claude SDK decision failed"
                        raise RuntimeError(msg)
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
        except asyncio.CancelledError:
            # 任务被取消，这是正常的(如 scheduler 停止时),不需要抛出异常
            logger.debug(f"Claude SDK decision cancelled for agent {invocation.agent_id}")
            return RuntimeDecision(action_type="rest")
        except RuntimeError as e:
            # Handle claude_agent_sdk anyio cancel scope errors
            if "cancel scope" in str(e).lower():
                logger.debug(f"Claude SDK cancel scope error for agent {invocation.agent_id}: {e}")
                return RuntimeDecision(action_type="rest")
            raise
        finally:
            # Properly close the async generator to avoid "cancel scope in different task" errors
            if gen is not None:
                try:
                    await gen.aclose()
                except RuntimeError as e:
                    if "cancel scope" not in str(e).lower():
                        raise

        if result_decision is None:
            msg = "Claude SDK returned no decision"
            raise RuntimeError(msg)

        return result_decision
