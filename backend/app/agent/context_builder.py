from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.agent.config_loader import AgentConfig

WorldFilterHook = Callable[[str, dict[str, Any]], dict[str, Any]]
RoleContextHook = Callable[[str, dict[str, Any]], dict[str, Any]]
SceneGuidanceHook = Callable[[str, dict[str, Any]], dict[str, Any]]
WorldKnowledgeHook = Callable[[], dict[str, Any]]


@dataclass(slots=True)
class ScenarioContextHooks:
    world_filter_hook: WorldFilterHook | None = None
    role_context_hook: RoleContextHook | None = None
    scene_guidance_hook: SceneGuidanceHook | None = None
    world_knowledge_hook: WorldKnowledgeHook | None = None


class ContextBuilder:
    """Builds simulation context for planner, reactor, and reflector."""

    def __init__(
        self,
        world_filter_hook: WorldFilterHook | None = None,
        role_context_hook: RoleContextHook | None = None,
        scene_guidance_hook: SceneGuidanceHook | None = None,
        world_knowledge_hook: WorldKnowledgeHook | None = None,
    ) -> None:
        self._hooks = ScenarioContextHooks(
            world_filter_hook=world_filter_hook,
            role_context_hook=role_context_hook,
            scene_guidance_hook=scene_guidance_hook,
            world_knowledge_hook=world_knowledge_hook,
        )

    def configure_policy(self, hooks: ScenarioContextHooks | None = None) -> None:
        self._hooks = hooks or ScenarioContextHooks()

    def configure_hooks(
        self,
        *,
        world_filter_hook: WorldFilterHook | None = None,
        role_context_hook: RoleContextHook | None = None,
        scene_guidance_hook: SceneGuidanceHook | None = None,
        world_knowledge_hook: WorldKnowledgeHook | None = None,
    ) -> None:
        self.configure_policy(
            ScenarioContextHooks(
                world_filter_hook=world_filter_hook,
                role_context_hook=role_context_hook,
                scene_guidance_hook=scene_guidance_hook,
                world_knowledge_hook=world_knowledge_hook,
            )
        )

    def build_base_context(
        self,
        agent: AgentConfig,
        world: dict[str, Any] | None = None,
        memory: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        filtered_world = self._filter_world_for_role(agent.world_role, world or {})
        return {
            "agent_id": agent.id,
            "agent_name": agent.name,
            "world_role": agent.world_role,
            "occupation": agent.occupation,
            "home": agent.home,
            "personality": agent.personality,
            "world": filtered_world,
            "memory": memory or {},
            "world_common_knowledge": self._build_world_knowledge(),
            "role_context": self._build_role_context(agent.world_role, filtered_world),
            "scene_guidance": self._build_scene_guidance(agent.world_role, filtered_world),
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
        recent_events: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        context = self.build_base_context(agent=agent, world=world, memory=memory)
        context["task"] = "reactor"
        context["event"] = event or {}
        context["recent_events"] = recent_events or []
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

    def _filter_world_for_role(
        self,
        world_role: str,
        world: dict[str, Any],
    ) -> dict[str, Any]:
        if self._hooks.world_filter_hook is not None:
            return self._hooks.world_filter_hook(world_role, world)
        return dict(world)

    def _build_role_context(self, world_role: str, world: dict[str, Any]) -> dict[str, Any]:
        if self._hooks.role_context_hook is not None:
            return self._hooks.role_context_hook(world_role, world)
        return {
            "perspective": "agent",
            "focus": "根据当前可见世界状态做连贯决策",
            "guidance": ["优先依据已知信息采取简单、稳定的动作"],
        }

    def _build_scene_guidance(self, world_role: str, world: dict[str, Any]) -> dict[str, Any]:
        if self._hooks.scene_guidance_hook is not None:
            return self._hooks.scene_guidance_hook(world_role, world)
        return {}

    def _build_world_knowledge(self) -> dict[str, Any]:
        if self._hooks.world_knowledge_hook is not None:
            return self._hooks.world_knowledge_hook()
        return {}
