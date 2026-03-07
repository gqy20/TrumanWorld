from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.agent.config_loader import AgentConfig
from app.agent.context_builder import ContextBuilder
from app.agent.prompt_loader import PromptLoader
from app.agent.registry import AgentRegistry


class RuntimeInvocation(BaseModel):
    agent_id: str
    task: str
    prompt: str
    context: dict[str, Any]
    max_turns: int
    max_budget_usd: float


class AgentRuntime:
    """Facade over Claude Agent SDK for TrumanWorld agents."""

    def __init__(
        self,
        registry: AgentRegistry,
        context_builder: ContextBuilder | None = None,
        prompt_loader: PromptLoader | None = None,
    ) -> None:
        self.registry = registry
        self.context_builder = context_builder or ContextBuilder()
        self.prompt_loader = prompt_loader or PromptLoader()

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
        prompt = self.registry.get_prompt(agent_id, context=context)
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
        prompt = self.registry.get_prompt(agent_id, context=context)
        return RuntimeInvocation(
            agent_id=agent_id,
            task="reactor",
            prompt=prompt or "",
            context=context,
            max_turns=config.model.max_turns,
            max_budget_usd=config.model.max_budget_usd,
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
        prompt = self.registry.get_prompt(agent_id, context=context)
        return RuntimeInvocation(
            agent_id=agent_id,
            task="reflector",
            prompt=prompt or "",
            context=context,
            max_turns=config.model.max_turns,
            max_budget_usd=config.model.max_budget_usd,
        )
