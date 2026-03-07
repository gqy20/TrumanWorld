from __future__ import annotations

from typing import Any

from app.agent.config_loader import AgentConfig


class ContextBuilder:
    """Builds simulation context for planner, reactor, and reflector."""

    def build_base_context(
        self,
        agent: AgentConfig,
        world: dict[str, Any] | None = None,
        memory: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "agent_id": agent.id,
            "agent_name": agent.name,
            "occupation": agent.occupation,
            "home": agent.home,
            "personality": agent.personality,
            "world": world or {},
            "memory": memory or {},
        }

    def build_planner_context(
        self,
        agent: AgentConfig,
        world: dict[str, Any] | None = None,
        memory: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        context = self.build_base_context(agent=agent, world=world, memory=memory)
        context["task"] = "planner"
        return context

    def build_reactor_context(
        self,
        agent: AgentConfig,
        world: dict[str, Any] | None = None,
        memory: dict[str, Any] | None = None,
        event: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        context = self.build_base_context(agent=agent, world=world, memory=memory)
        context["task"] = "reactor"
        context["event"] = event or {}
        return context

    def build_reflector_context(
        self,
        agent: AgentConfig,
        world: dict[str, Any] | None = None,
        memory: dict[str, Any] | None = None,
        daily_summary: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        context = self.build_base_context(agent=agent, world=world, memory=memory)
        context["task"] = "reflector"
        context["daily_summary"] = daily_summary or {}
        return context
