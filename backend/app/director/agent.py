"""Director Agent - LLM-based intelligent director decision system.

This module provides the DirectorAgent class that uses LLM to make
intelligent intervention decisions based on world state observation.
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from app.director.observer import DirectorAssessment
from app.director.types import DirectorPlan
from app.infra.logging import get_logger
from app.infra.settings import get_settings
from app.scenario.truman_world.director_config import load_director_config
from app.scenario.types import get_agent_config_id, get_world_role

if TYPE_CHECKING:
    from claude_agent_sdk import ClaudeAgentOptions

logger = get_logger(__name__)

# Director decision output schema for LLM
DIRECTOR_DECISION_SCHEMA = {
    "type": "object",
    "properties": {
        "should_intervene": {"type": "boolean"},
        "scene_goal": {
            "type": "string",
            "enum": [
                "soft_check_in",
                "preemptive_comfort",
                "keep_scene_natural",
                "break_isolation",
                "rejection_recovery",
                "none",
            ],
        },
        "target_cast_names": {"type": "array", "items": {"type": "string"}},
        "priority": {"type": "string", "enum": ["low", "normal", "high", "critical"]},
        "urgency": {"type": "string", "enum": ["advisory", "immediate", "emergency"]},
        "reasoning": {"type": "string"},
        "message_hint": {"type": "string"},
        "strategy": {"type": "string"},
        "cooldown_ticks": {"type": "integer", "minimum": 1, "maximum": 10},
    },
    "required": ["should_intervene", "scene_goal"],
    "additionalProperties": False,
}


@dataclass
class DirectorContext:
    """Context for director decision making."""

    run_id: str
    current_tick: int
    assessment: DirectorAssessment
    agents: list[dict[str, Any]]  # 纯 dict 快照，脱离 SQLAlchemy session，避免 greenlet 冲突
    recent_events: list[dict[str, Any]]
    recent_interventions: list[dict[str, Any]]
    world_time: str


class DirectorAgent:
    """LLM-based director agent for intelligent intervention decisions.

    The DirectorAgent observes the world state and uses LLM to decide
    whether and how to intervene, providing rich reasoning and strategy.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self._config = load_director_config()
        # Use settings as fallback, but config takes precedence
        self._enabled = self._config.enabled and self.settings.director_agent_enabled
        self._decision_interval = self._config.decision_interval
        self._model = (
            self._config.llm.model
            or self.settings.director_agent_model
            or self.settings.agent_model
        )

    def is_enabled(self) -> bool:
        """Check if director agent is enabled."""
        return self._enabled

    def should_decide(self, tick_no: int) -> bool:
        """Check if should make LLM decision at this tick."""
        if not self._enabled:
            return False
        return tick_no % self._decision_interval == 0

    def reload_config(self) -> None:
        """Reload configuration from file (for hot-reloading)."""
        self._config = load_director_config(force_reload=True)
        self._enabled = self._config.enabled and self.settings.director_agent_enabled
        self._decision_interval = self._config.decision_interval
        self._model = (
            self._config.llm.model
            or self.settings.director_agent_model
            or self.settings.agent_model
        )
        logger.debug("DirectorAgent configuration reloaded")

    async def decide(
        self,
        context: DirectorContext,
        recent_goals: set[str],
    ) -> DirectorPlan | None:
        """Make an intelligent intervention decision using LLM.

        Args:
            context: Director context including assessment and world state
            recent_goals: Recently executed intervention goals to avoid repetition

        Returns:
            DirectorPlan if intervention is needed, None otherwise
        """
        if not self._enabled:
            return None

        cast_agents = [a for a in context.agents if get_world_role(a.get("profile")) == "cast"]
        if not cast_agents or context.assessment.truman_agent_id is None:
            return None

        # Build prompt for LLM
        prompt = self._build_decision_prompt(context, cast_agents, recent_goals)

        try:
            # Call LLM for decision
            response = await self._call_llm(prompt)
            return self._parse_response(response, context, cast_agents)
        except Exception as exc:
            logger.warning(f"DirectorAgent LLM decision failed: {exc}")
            return None

    def _build_decision_prompt(
        self,
        context: DirectorContext,
        cast_agents: list[dict[str, Any]],
        recent_goals: set[str],
    ) -> str:
        """Build the decision prompt for LLM using configuration template."""
        # Build cast agents info
        cast_info = []
        for agent in sorted(cast_agents, key=lambda a: a.get("name", "")):
            config_id = get_agent_config_id(agent.get("profile")) or "unknown"
            cast_info.append(
                f"- {agent.get('name')} (role: {config_id}, location: {agent.get('current_location_id')})"
            )

        # Build recent events summary (using config limit)
        recent_events_limit = self._config.prompt.recent_events_limit
        events_summary = []
        for event in context.recent_events[-recent_events_limit:]:
            events_summary.append(
                f"  - tick {event.get('tick_no')}: {event.get('event_type')} - {event.get('description', 'N/A')}"
            )

        # Build recent interventions (using config limit)
        recent_interventions_limit = self._config.prompt.recent_interventions_limit
        interventions_summary = []
        for intervention in context.recent_interventions[-recent_interventions_limit:]:
            interventions_summary.append(
                f"  - tick {intervention.get('tick_no')}: {intervention.get('scene_goal')} - {intervention.get('reason', 'N/A')[:50]}..."
            )

        # Build scene goals info
        scene_goals_info = []
        for goal_id, goal_data in self._config.scene_goals.items():
            desc = goal_data.get("description", "")
            priority = goal_data.get("priority", "normal")
            scene_goals_info.append(f"- {goal_id}: {desc} (priority: {priority})")

        # Assessment details
        assessment = context.assessment

        # Build context for template rendering
        prompt_context = {
            "world_time": context.world_time,
            "current_tick": context.current_tick,
            "run_id": context.run_id,
            "truman_agent_id": assessment.truman_agent_id or "unknown",
            "truman_suspicion_score": f"{assessment.truman_suspicion_score:.2f}",
            "suspicion_level": assessment.suspicion_level,
            "truman_isolation_ticks": assessment.truman_isolation_ticks,
            "recent_rejections": assessment.recent_rejections,
            "continuity_risk": assessment.continuity_risk,
            "cast_agents_info": chr(10).join(cast_info) if cast_info else "(none)",
            "recent_events_limit": recent_events_limit,
            "recent_events_info": chr(10).join(events_summary)
            if events_summary
            else "(no recent events)",
            "recent_interventions_limit": recent_interventions_limit,
            "recent_interventions_info": chr(10).join(interventions_summary)
            if interventions_summary
            else "(no recent interventions)",
            "recent_goals_info": ", ".join(recent_goals) if recent_goals else "(none)",
            "scene_goals_info": chr(10).join(scene_goals_info)
            if scene_goals_info
            else "(none defined)",
        }

        # Render prompt using configuration template
        return self._config.render_prompt(prompt_context)

    async def _call_llm(self, prompt: str) -> str:
        """Call LLM for decision using Claude SDK.

        Uses the same LLM infrastructure as agent decisions.
        Uses configuration from director.yml for LLM parameters.
        """
        from app.cognition.claude.sdk_options import build_sdk_options

        logger.debug("DirectorAgent calling LLM for decision")

        # Check if Claude CLI is available
        import shutil

        if shutil.which("claude") is None:
            logger.warning("Claude CLI not available, falling back to mock")
            return self._mock_llm_response()

        # Build options from configuration
        llm_config = self._config.llm
        options = build_sdk_options(
            self.settings,
            max_turns=llm_config.max_turns,
            max_budget_usd=llm_config.max_budget_usd,
            model=self._model,
            cwd=str(self.settings.project_root),
            system_prompt="You are the Director of a simulation. You make decisions about when and how to intervene.",
        )

        # Add JSON schema to prompt
        json_schema = json.dumps(DIRECTOR_DECISION_SCHEMA, indent=2)
        full_prompt = f"""{prompt}

重要：你必须只返回一个有效的 JSON 对象，不要有其他任何文本。JSON 格式如下:
{json_schema}

返回 JSON，不要有 markdown 代码块标记。"""

        try:
            return await self._call_llm_internal(full_prompt, options)
        except asyncio.CancelledError:
            # 任务被取消，这是正常的，不需要抛出异常
            logger.debug("DirectorAgent LLM call cancelled")
            return self._mock_llm_response()
        except RuntimeError as e:
            # Handle claude_agent_sdk anyio cancel scope errors
            if "cancel scope" in str(e).lower() or "different task" in str(e).lower():
                logger.debug(f"DirectorAgent cancel scope error: {e}")
                return self._mock_llm_response()
            raise
        except Exception as exc:
            logger.warning(f"DirectorAgent LLM call failed: {exc}, using mock")
            return self._mock_llm_response()

    async def _call_llm_internal(self, full_prompt: str, options: "ClaudeAgentOptions") -> str:
        """Internal LLM call - separated to handle SDK cleanup issues."""
        from claude_agent_sdk import query

        gen = None
        try:
            gen = query(prompt=full_prompt, options=options)
            async for message in gen:
                if hasattr(message, "is_error") and message.is_error:
                    msg = getattr(message, "result", None) or "DirectorAgent LLM call failed"
                    raise RuntimeError(msg)

                # Extract result
                result = getattr(message, "result", None)
                if result:
                    text = result.strip()
                    # Remove markdown code block markers if present
                    if text.startswith("```"):
                        text = re.sub(r"^```json?\n?", "", text)
                        text = re.sub(r"\n?```$", "", text)
                    text = text.strip()

                    # Log token usage if available
                    usage = getattr(message, "usage", None)
                    if usage:
                        logger.debug(f"DirectorAgent LLM usage: {usage}")

                    return text

            raise RuntimeError("DirectorAgent LLM returned no result")
        finally:
            # Properly close the async generator
            if gen is not None:
                try:
                    await gen.aclose()
                except RuntimeError:
                    # Ignore "cancel scope in different task" errors - this is a known SDK issue
                    pass

    def _mock_llm_response(self) -> str:
        """Return a mock response for testing or when LLM is unavailable."""
        import random

        # Simulate occasional interventions for testing
        if random.random() < 0.3:  # 30% chance of intervention for testing
            return json.dumps(
                {
                    "should_intervene": True,
                    "scene_goal": "break_isolation",
                    "target_cast_names": ["Alice"],
                    "priority": "normal",
                    "urgency": "advisory",
                    "reasoning": "Truman has been isolated for several ticks. A natural encounter would help maintain engagement.",
                    "message_hint": "You happen to be going to the same location as Truman. Keep it natural, don't force interaction.",
                    "strategy": "Natural encounter to break isolation",
                    "cooldown_ticks": 4,
                }
            )

        return json.dumps({"should_intervene": False, "scene_goal": "none"})

    def _parse_response(
        self,
        response: str,
        context: DirectorContext,
        cast_agents: list[dict[str, Any]],
    ) -> DirectorPlan | None:
        """Parse LLM response into DirectorPlan."""
        try:
            # Extract JSON from response (handle markdown code blocks)
            json_str = response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()

            data = json.loads(json_str)

            if not data.get("should_intervene", False):
                return None

            scene_goal = data.get("scene_goal", "none")
            if scene_goal == "none":
                return None

            # Map cast names to agent IDs
            target_cast_names = data.get("target_cast_names", [])
            target_cast_ids = []
            for name in target_cast_names:
                for agent in cast_agents:
                    if (agent.get("name") or "").lower() == name.lower():
                        target_cast_ids.append(agent.get("id", ""))
                        break

            if not target_cast_ids and cast_agents:
                # Fallback to first cast agent if names don't match
                target_cast_ids = [cast_agents[0].get("id", "")]

            return DirectorPlan(
                scene_goal=scene_goal,
                target_cast_ids=target_cast_ids,
                priority=data.get("priority", "normal"),
                urgency=data.get("urgency", "advisory"),
                message_hint=data.get("message_hint"),
                target_agent_id=context.assessment.truman_agent_id,
                reason=data.get("reasoning", "LLM-based intervention decision"),
                cooldown_ticks=data.get("cooldown_ticks", 3),
            )

        except json.JSONDecodeError as exc:
            logger.warning(f"Failed to parse DirectorAgent response: {exc}")
            return None
        except Exception as exc:
            logger.warning(f"Error parsing DirectorAgent response: {exc}")
            return None
