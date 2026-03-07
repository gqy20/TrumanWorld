from __future__ import annotations

import asyncio
import json
import shutil
from abc import ABC, abstractmethod
from typing import Any

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query
from pydantic import BaseModel, Field

from app.infra.settings import Settings


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

    async def decide(self, invocation: Any) -> RuntimeDecision:
        if shutil.which("claude") is None:
            msg = "Claude CLI is not available in the current environment"
            raise RuntimeError(msg)

        env = {}
        if self.settings.anthropic_api_key:
            env["ANTHROPIC_API_KEY"] = self.settings.anthropic_api_key
        if self.settings.anthropic_base_url:
            env["ANTHROPIC_BASE_URL"] = self.settings.anthropic_base_url

        options = ClaudeAgentOptions(
            max_turns=invocation.max_turns,
            max_budget_usd=invocation.max_budget_usd,
            model=self.settings.agent_model,
            cwd=str(self.settings.project_root),
            env=env,
            output_format=DECISION_OUTPUT_SCHEMA,
        )

        try:
            async for message in query(prompt=invocation.prompt, options=options):
                if isinstance(message, ResultMessage):
                    if message.is_error:
                        msg = message.result or "Claude SDK decision failed"
                        raise RuntimeError(msg)
                    if message.structured_output is not None:
                        return RuntimeDecision.model_validate(message.structured_output)
                    if message.result:
                        try:
                            return RuntimeDecision.model_validate(json.loads(message.result))
                        except json.JSONDecodeError as exc:
                            msg = "Claude SDK returned non-JSON decision output"
                            raise RuntimeError(msg) from exc
        except asyncio.CancelledError as exc:
            msg = "Claude SDK decision cancelled"
            raise RuntimeError(msg) from exc
        except Exception as exc:
            msg = f"Claude SDK decision failed: {exc}"
            raise RuntimeError(msg) from exc

        msg = "Claude SDK returned no decision"
        raise RuntimeError(msg)
