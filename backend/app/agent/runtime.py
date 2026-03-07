from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.agent.config_loader import AgentConfig
from app.agent.context_builder import ContextBuilder
from app.agent.providers import (
    AgentDecisionProvider,
    ClaudeSDKDecisionProvider,
    HeuristicDecisionProvider,
)
from app.agent.prompt_loader import PromptLoader
from app.agent.registry import AgentRegistry
from app.infra.settings import get_settings
from app.sim.action_resolver import ActionIntent


class RuntimeInvocation(BaseModel):
    agent_id: str
    task: str
    prompt: str
    context: dict[str, Any]
    max_turns: int
    max_budget_usd: float
    allowed_actions: list[str] = []


class AgentRuntime:
    """Facade over Claude Agent SDK for TrumanWorld agents."""

    def __init__(
        self,
        registry: AgentRegistry,
        context_builder: ContextBuilder | None = None,
        prompt_loader: PromptLoader | None = None,
        decision_provider: AgentDecisionProvider | None = None,
    ) -> None:
        self.registry = registry
        self.context_builder = context_builder or ContextBuilder()
        self.prompt_loader = prompt_loader or PromptLoader()
        self.decision_provider = decision_provider or self._build_default_provider()

    def _build_default_provider(self) -> AgentDecisionProvider:
        settings = get_settings()
        if settings.agent_provider == "claude":
            return ClaudeSDKDecisionProvider(settings)
        return HeuristicDecisionProvider()

    def _load_agent(self, agent_id: str) -> AgentConfig:
        config = self.registry.get_config(agent_id)
        if config is None:
            msg = f"Agent config not found for '{agent_id}'"
            raise ValueError(msg)
        return config

    def prepare_planner(
        self,
        agent_id: str,
        world: dict[str, Any] | None = None,
        memory: dict[str, Any] | None = None,
    ) -> RuntimeInvocation:
        config = self._load_agent(agent_id)
        context = self.context_builder.build_planner_context(config, world=world, memory=memory)
        base_prompt = self.registry.get_prompt(agent_id)
        prompt = self.prompt_loader.render(base_prompt or "", context=context)
        return RuntimeInvocation(
            agent_id=agent_id,
            task="planner",
            prompt=prompt or "",
            context=context,
            max_turns=config.model.max_turns,
            max_budget_usd=config.model.max_budget_usd,
        )

    def prepare_reactor(
        self,
        agent_id: str,
        world: dict[str, Any] | None = None,
        memory: dict[str, Any] | None = None,
        event: dict[str, Any] | None = None,
    ) -> RuntimeInvocation:
        config = self._load_agent(agent_id)
        context = self.context_builder.build_reactor_context(
            config,
            world=world,
            memory=memory,
            event=event,
        )
        base_prompt = self.registry.get_prompt(agent_id)
        allowed_actions = ["move", "talk", "work", "rest"]
        prompt = self.prompt_loader.render_decision_prompt(
            base_prompt or "",
            context=context,
            allowed_actions=allowed_actions,
        )
        return RuntimeInvocation(
            agent_id=agent_id,
            task="reactor",
            prompt=prompt or "",
            context=context,
            max_turns=config.model.max_turns,
            max_budget_usd=config.model.max_budget_usd,
            allowed_actions=allowed_actions,
        )

    def prepare_reflector(
        self,
        agent_id: str,
        world: dict[str, Any] | None = None,
        memory: dict[str, Any] | None = None,
        daily_summary: dict[str, Any] | None = None,
    ) -> RuntimeInvocation:
        config = self._load_agent(agent_id)
        context = self.context_builder.build_reflector_context(
            config,
            world=world,
            memory=memory,
            daily_summary=daily_summary,
        )
        base_prompt = self.registry.get_prompt(agent_id)
        prompt = self.prompt_loader.render(base_prompt or "", context=context)
        return RuntimeInvocation(
            agent_id=agent_id,
            task="reflector",
            prompt=prompt or "",
            context=context,
            max_turns=config.model.max_turns,
            max_budget_usd=config.model.max_budget_usd,
        )

    async def decide_intent(self, invocation: RuntimeInvocation) -> ActionIntent:
        decision = await self.decision_provider.decide(invocation)
        return ActionIntent(
            agent_id=invocation.agent_id,
            action_type=decision.action_type,
            target_location_id=decision.target_location_id,
            target_agent_id=decision.target_agent_id,
            payload=decision.payload,
        )

    async def react(
        self,
        agent_id: str,
        world: dict[str, Any] | None = None,
        memory: dict[str, Any] | None = None,
        event: dict[str, Any] | None = None,
    ) -> ActionIntent:
        invocation = self.prepare_reactor(agent_id, world=world, memory=memory, event=event)
        return await self.decide_intent(invocation)

    def derive_intent(self, invocation: RuntimeInvocation) -> ActionIntent:
        world = invocation.context.get("world", {})
        goal = world.get("current_goal")
        current_location_id = world.get("current_location_id")
        home_location_id = world.get("home_location_id")
        nearby_agent_id = world.get("nearby_agent_id")

        if isinstance(goal, str) and goal.startswith("move:"):
            target_location_id = goal.split(":", 1)[1].strip()
            return ActionIntent(
                agent_id=invocation.agent_id,
                action_type="move",
                target_location_id=target_location_id,
            )

        if goal == "work":
            return ActionIntent(agent_id=invocation.agent_id, action_type="work")

        if goal == "talk" and nearby_agent_id:
            return ActionIntent(
                agent_id=invocation.agent_id,
                action_type="talk",
                target_agent_id=str(nearby_agent_id),
            )

        if (
            current_location_id
            and home_location_id
            and current_location_id != home_location_id
            and goal == "go_home"
        ):
            return ActionIntent(
                agent_id=invocation.agent_id,
                action_type="move",
                target_location_id=str(home_location_id),
            )

        return ActionIntent(agent_id=invocation.agent_id, action_type="rest")
