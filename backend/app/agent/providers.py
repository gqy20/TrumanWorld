from __future__ import annotations

import asyncio
import json
import logging
import re
import shutil
from abc import ABC, abstractmethod
from typing import Any

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query
from pydantic import BaseModel, Field, ValidationError

from app.infra.settings import Settings

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
        "payload": {"type": "object"},
    },
    "required": ["action_type"],
    "additionalProperties": False,
}


class RuntimeDecision(BaseModel):
    action_type: str
    target_location_id: str | None = None
    target_agent_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class AgentDecisionProvider(ABC):
    @abstractmethod
    async def decide(self, invocation: Any) -> RuntimeDecision:
        raise NotImplementedError


class HeuristicDecisionProvider(AgentDecisionProvider):
    async def decide(self, invocation: Any) -> RuntimeDecision:
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
            )

        if current_location_id and home_location_id and current_location_id != home_location_id and goal == "go_home":
            return RuntimeDecision(
                action_type="move",
                target_location_id=str(home_location_id),
            )

        return RuntimeDecision(action_type="rest")


class ClaudeSDKDecisionProvider(AgentDecisionProvider):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def decide(self, invocation: RuntimeInvocation) -> RuntimeDecision:
        if shutil.which("claude") is None:
            msg = "Claude CLI is not available in the current environment"
            raise RuntimeError(msg)

        env = {}
        if self.settings.anthropic_api_key:
            env["ANTHROPIC_API_KEY"] = self.settings.anthropic_api_key
        if self.settings.anthropic_base_url:
            env["ANTHROPIC_BASE_URL"] = self.settings.anthropic_base_url

        # Note: output_format is not supported by MiniMax API
        # Use global budget setting as fallback if invocation budget is too low
        budget = invocation.max_budget_usd if invocation.max_budget_usd >= 0.1 else self.settings.agent_budget_usd
        options = ClaudeAgentOptions(
            max_turns=invocation.max_turns,
            max_budget_usd=budget,
            model=self.settings.agent_model,
            cwd=str(self.settings.project_root),
            env=env,
        )

        # Build prompt that asks for JSON response
        json_schema = json.dumps(DECISION_OUTPUT_SCHEMA, indent=2)
        full_prompt = f"""{invocation.prompt}

重要：你必须只返回一个有效的 JSON 对象，不要有其他任何文本。JSON 格式如下：
{json_schema}

只返回 JSON，不要有 markdown 代码块标记。"""

        # Call SDK and parse result
        # Note: We don't use asyncio.shield here because it causes issues with SQLAlchemy's greenlet
        result_decision: RuntimeDecision | None = None
        
        try:
            async for message in query(prompt=full_prompt, options=options):
                if isinstance(message, ResultMessage):
                    if message.is_error:
                        msg = message.result or "Claude SDK decision failed"
                        raise RuntimeError(msg)
                    # Parse JSON from text response
                    if message.result:
                        try:
                            # Try to extract JSON - use a more robust approach
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
            # 任务被取消，这是正常的（如 scheduler 停止时），不需要抛出异常
            logger.debug(f"Claude SDK decision cancelled for agent {invocation.agent_id}")
            return RuntimeDecision(action_type="rest")
        except RuntimeError as e:
            # Handle claude_agent_sdk anyio cancel scope errors
            if "cancel scope" in str(e).lower():
                logger.debug(f"Claude SDK cancel scope error for agent {invocation.agent_id}: {e}")
                return RuntimeDecision(action_type="rest")
            raise
        
        if result_decision is None:
            msg = "Claude SDK returned no decision"
            raise RuntimeError(msg)
        
        return result_decision
