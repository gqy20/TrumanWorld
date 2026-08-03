from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.scenario.bundle_world.default_modules import (
    DefaultAgentContextPolicy,
    DefaultAllowedActionsPolicy,
    DefaultDirectorPolicy,
    DefaultFallbackPolicy,
    DefaultProfileMergePolicy,
    EmbodiedAllowedActionsPolicy,
)
from app.scenario.bundle_world.seed import BundleWorldSeedBuilder
from app.scenario.bundle_world.state import BundleWorldStateUpdater


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
_registry.register_allowed_actions_policy("embodied_actions", EmbodiedAllowedActionsPolicy)
_registry.register_profile_merge_policy("director_guidance_merge", DefaultProfileMergePolicy)


def get_bundle_world_module_registry() -> BundleWorldModuleRegistry:
    return _registry
