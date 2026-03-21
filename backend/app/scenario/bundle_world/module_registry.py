from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.agent.context_builder import ScenarioContextHooks
from app.scenario.bundle_world.coordinator import BundleWorldCoordinator
from app.scenario.bundle_world.heuristics import build_bundle_world_decision
from app.scenario.bundle_world.rules import (
    build_role_context,
    build_scene_guidance,
    build_world_common_knowledge,
    filter_world_for_role,
)
from app.scenario.bundle_world.seed import BundleWorldSeedBuilder
from app.scenario.bundle_world.state import BundleWorldStateUpdater
from app.scenario.bundle_world.types import (
    BundleWorldGuidance,
    build_bundle_world_guidance,
    merge_bundle_world_agent_profile,
)
from app.scenario.runtime_config import RuntimeRoleSemantics
from app.sim.action_resolver import ActionIntent
from app.sim.types import RuntimeWorldContext


class DefaultFallbackPolicy:
    def __init__(self, *, scenario_id: str, semantics: RuntimeRoleSemantics) -> None:
        self.scenario_id = scenario_id
        self.semantics = semantics

    def configure_runtime(self, agent_runtime) -> None:
        agent_runtime.configure_fallback_decision_hook(self.build_runtime_decision)

    def build_runtime_decision(
        self,
        world: RuntimeWorldContext,
        nearby_agent_id: str | None,
        current_location_id: str | None,
        home_location_id: str | None,
        agent_id: str | None = None,
    ):
        return build_bundle_world_decision(
            world=world,
            nearby_agent_id=nearby_agent_id,
            current_location_id=current_location_id,
            home_location_id=home_location_id,
            agent_id=agent_id,
            semantics=self.semantics,
        )

    def fallback_intent(
        self,
        *,
        agent_id: str,
        current_location_id: str,
        home_location_id: str | None,
        nearby_agent_id: str | None,
        world_role: str | None = None,
        current_status: dict | None = None,
        scenario_state: dict | None = None,
        scenario_guidance=None,
    ) -> ActionIntent | None:
        subject_alert_score = float((scenario_state or {}).get("subject_alert_score") or 0.0)
        director_guidance: BundleWorldGuidance = {}
        if scenario_guidance:
            director_guidance = build_bundle_world_guidance(
                scene_goal=scenario_guidance.get("scene_goal")
                or scenario_guidance.get("director_scene_goal"),
                priority=scenario_guidance.get("priority")
                or scenario_guidance.get("director_priority"),
                message_hint=scenario_guidance.get("message_hint")
                or scenario_guidance.get("director_message_hint"),
                target_agent_id=scenario_guidance.get("target_agent_id")
                or scenario_guidance.get("director_target_agent_id"),
                location_hint=scenario_guidance.get("location_hint")
                or scenario_guidance.get("director_location_hint"),
                reason=scenario_guidance.get("reason") or scenario_guidance.get("director_reason"),
            )
        runtime_world: RuntimeWorldContext = {
            "world_role": world_role,
            "self_status": current_status or {},
            "subject_alert_score": subject_alert_score,
            **director_guidance,
        }
        decision = build_bundle_world_decision(
            world=runtime_world,
            nearby_agent_id=nearby_agent_id,
            current_location_id=current_location_id,
            home_location_id=home_location_id,
            semantics=self.semantics,
        )
        if decision is None:
            return None
        payload = dict(decision.payload)
        if decision.message:
            payload["message"] = decision.message
        return ActionIntent(
            agent_id=agent_id,
            action_type=decision.action_type,
            target_location_id=decision.target_location_id,
            target_agent_id=decision.target_agent_id,
            payload=payload,
        )


class DefaultDirectorPolicy:
    def __init__(self, session, *, scenario_id: str) -> None:
        self.coordinator = BundleWorldCoordinator(session, scenario_id=scenario_id)

    async def observe_run(self, run_id: str, event_limit: int = 20):
        return await self.coordinator.observe_run(run_id, event_limit=event_limit)

    def assess(
        self,
        *,
        run_id: str,
        current_tick: int,
        agents: list,
        events: list,
    ):
        return self.coordinator.assess(
            run_id=run_id,
            current_tick=current_tick,
            agents=agents,
            events=events,
        )

    async def build_director_plan(self, run_id: str, agents: list):
        return await self.coordinator.build_director_plan(run_id, agents)

    async def persist_director_plan(self, run_id: str, plan) -> None:
        await self.coordinator.persist_director_plan(run_id, plan)


class DefaultAgentContextPolicy:
    def __init__(self, *, scenario_id: str, semantics: RuntimeRoleSemantics) -> None:
        self.scenario_id = scenario_id
        self.semantics = semantics

    def configure_agent_context(self, context_builder) -> None:
        context_builder.configure_policy(
            ScenarioContextHooks(
                world_filter_hook=lambda world_role, world: filter_world_for_role(
                    world_role, world, semantics=self.semantics
                ),
                role_context_hook=lambda world_role, world: build_role_context(
                    world_role, world, semantics=self.semantics
                ),
                scene_guidance_hook=lambda world_role, world: build_scene_guidance(
                    world_role, world, semantics=self.semantics
                ),
                world_knowledge_hook=lambda: build_world_common_knowledge(self.scenario_id),
            )
        )


class DefaultAllowedActionsPolicy:
    def __init__(self, *, actions: list[str] | None = None) -> None:
        self._actions = list(actions or ["move", "talk", "work", "rest"])

    def configure_runtime(self, agent_runtime) -> None:
        agent_runtime.configure_allowed_actions(self.allowed_actions())

    def allowed_actions(self) -> list[str]:
        return list(self._actions)


class DefaultProfileMergePolicy:
    def merge_agent_profile(self, agent, plan):
        guidance = {}
        if plan and agent.id in plan.target_agent_ids:
            guidance = build_bundle_world_guidance(
                scene_goal=plan.scene_goal,
                priority=plan.priority,
                message_hint=plan.message_hint,
                target_agent_id=plan.target_agent_id,
                location_hint=plan.location_hint,
                reason=plan.reason,
            )
        return merge_bundle_world_agent_profile(agent.profile or {}, guidance)


FallbackPolicyFactory = Callable[..., Any]
SeedPolicyFactory = Callable[..., Any]
StateUpdatePolicyFactory = Callable[..., Any]
DirectorPolicyFactory = Callable[..., Any]
AgentContextPolicyFactory = Callable[..., Any]
AllowedActionsPolicyFactory = Callable[..., Any]
ProfileMergePolicyFactory = Callable[..., Any]


@dataclass
class BundleWorldModuleRegistry:
    fallback_policies: dict[str, FallbackPolicyFactory] = field(default_factory=dict)
    seed_policies: dict[str, SeedPolicyFactory] = field(default_factory=dict)
    state_update_policies: dict[str, StateUpdatePolicyFactory] = field(default_factory=dict)
    director_policies: dict[str, DirectorPolicyFactory] = field(default_factory=dict)
    agent_context_policies: dict[str, AgentContextPolicyFactory] = field(default_factory=dict)
    allowed_actions_policies: dict[str, AllowedActionsPolicyFactory] = field(default_factory=dict)
    profile_merge_policies: dict[str, ProfileMergePolicyFactory] = field(default_factory=dict)

    def register_fallback_policy(self, module_id: str, factory: FallbackPolicyFactory) -> None:
        self.fallback_policies[module_id] = factory

    def register_seed_policy(self, module_id: str, factory: SeedPolicyFactory) -> None:
        self.seed_policies[module_id] = factory

    def register_state_update_policy(
        self, module_id: str, factory: StateUpdatePolicyFactory
    ) -> None:
        self.state_update_policies[module_id] = factory

    def register_director_policy(self, module_id: str, factory: DirectorPolicyFactory) -> None:
        self.director_policies[module_id] = factory

    def register_agent_context_policy(
        self, module_id: str, factory: AgentContextPolicyFactory
    ) -> None:
        self.agent_context_policies[module_id] = factory

    def register_allowed_actions_policy(
        self, module_id: str, factory: AllowedActionsPolicyFactory
    ) -> None:
        self.allowed_actions_policies[module_id] = factory

    def register_profile_merge_policy(
        self, module_id: str, factory: ProfileMergePolicyFactory
    ) -> None:
        self.profile_merge_policies[module_id] = factory

    def build_fallback_policy(self, module_id: str, **kwargs):
        return self.fallback_policies[module_id](**kwargs)

    def build_seed_policy(self, module_id: str, *args, **kwargs):
        return self.seed_policies[module_id](*args, **kwargs)

    def build_state_update_policy(self, module_id: str, *args, **kwargs):
        return self.state_update_policies[module_id](*args, **kwargs)

    def build_director_policy(self, module_id: str, *args, **kwargs):
        return self.director_policies[module_id](*args, **kwargs)

    def build_agent_context_policy(self, module_id: str, **kwargs):
        return self.agent_context_policies[module_id](**kwargs)

    def build_allowed_actions_policy(self, module_id: str, **kwargs):
        return self.allowed_actions_policies[module_id](**kwargs)

    def build_profile_merge_policy(self, module_id: str, *args, **kwargs):
        return self.profile_merge_policies[module_id](*args, **kwargs)


_registry = BundleWorldModuleRegistry()
_registry.register_fallback_policy("social_default", DefaultFallbackPolicy)
_registry.register_seed_policy("standard_bundle_seed", BundleWorldSeedBuilder)
_registry.register_state_update_policy("alert_tracking", BundleWorldStateUpdater)
_registry.register_director_policy("standard_director", DefaultDirectorPolicy)
_registry.register_agent_context_policy("standard_context", DefaultAgentContextPolicy)
_registry.register_allowed_actions_policy("standard_actions", DefaultAllowedActionsPolicy)
_registry.register_profile_merge_policy("director_guidance_merge", DefaultProfileMergePolicy)


def get_bundle_world_module_registry() -> BundleWorldModuleRegistry:
    return _registry
