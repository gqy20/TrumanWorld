from __future__ import annotations

from typing import TYPE_CHECKING

from app.scenario.base import Scenario
from app.scenario.bundle_registry import get_scenario_bundle
from app.scenario.bundle_world.module_registry import get_bundle_world_module_registry
from app.scenario.bundle_world.state import build_alert_state_semantics
from app.scenario.runtime_config import build_scenario_runtime_config
from app.scenario.types import AgentProfile, ScenarioGuidance

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.agent.runtime import AgentRuntime
    from app.store.models import Agent, Event, SimulationRun


class BundleWorldScenario(Scenario):
    def __init__(
        self,
        session: AsyncSession | None = None,
        *,
        scenario_id: str = "narrative_world",
    ) -> None:
        self.session = session
        self.scenario_id = scenario_id
        bundle = get_scenario_bundle(scenario_id)
        capabilities = bundle.capabilities if bundle is not None else None
        modules = bundle.modules if bundle is not None else None
        self.runtime_config = build_scenario_runtime_config(scenario_id)
        self.module_ids = {
            "fallback_policy": modules.fallback_policy if modules is not None else None,
            "seed_policy": modules.seed_policy if modules is not None else None,
            "state_update_policy": modules.state_update_policy if modules is not None else None,
            "director_policy": modules.director_policy if modules is not None else None,
            "agent_context_policy": (
                modules.agent_context_policy if modules is not None else None
            ),
            "allowed_actions_policy": (
                modules.allowed_actions_policy if modules is not None else None
            ),
            "profile_merge_policy": (
                modules.profile_merge_policy if modules is not None else None
            ),
        }
        self.subject_alert_tracking_enabled = (
            capabilities.subject_alert_tracking
            if capabilities is not None and capabilities.subject_alert_tracking is not None
            else True
        )
        module_registry = get_bundle_world_module_registry()
        self.director_policy = module_registry.build_director_policy(
            self.module_ids["director_policy"] or "standard_director",
            session,
            scenario_id=scenario_id,
        )
        self.coordinator = getattr(self.director_policy, "coordinator", None)
        self.fallback_policy = module_registry.build_fallback_policy(
            self.module_ids["fallback_policy"] or "social_default",
            scenario_id=scenario_id,
            semantics=self.runtime_config,
        )
        self.agent_context_policy = module_registry.build_agent_context_policy(
            self.module_ids["agent_context_policy"] or "standard_context",
            scenario_id=scenario_id,
            semantics=self.runtime_config,
        )
        self.allowed_actions_policy = module_registry.build_allowed_actions_policy(
            self.module_ids["allowed_actions_policy"] or "standard_actions",
        )
        self.profile_merge_policy = module_registry.build_profile_merge_policy(
            self.module_ids["profile_merge_policy"] or "director_guidance_merge",
        )
        self.state_updater = (
            module_registry.build_state_update_policy(
                self.module_ids["state_update_policy"] or "alert_tracking",
                session,
                semantics=build_alert_state_semantics(scenario_id),
            )
            if session is not None and self.subject_alert_tracking_enabled
            else None
        )
        self.seed_builder = (
            module_registry.build_seed_policy(
                self.module_ids["seed_policy"] or "standard_bundle_seed",
                session,
                scenario_id=scenario_id,
            )
            if session is not None
            else None
        )

    def with_session(self, session: AsyncSession | None) -> BundleWorldScenario:
        return BundleWorldScenario(session, scenario_id=self.scenario_id)

    def configure_runtime(self, agent_runtime: AgentRuntime) -> None:
        self.allowed_actions_policy.configure_runtime(agent_runtime)
        self.fallback_policy.configure_runtime(agent_runtime)
        self.configure_agent_context(agent_runtime.context_builder)

    def configure_agent_context(self, context_builder) -> None:
        self.agent_context_policy.configure_agent_context(context_builder)

    async def observe_run(self, run_id: str, event_limit: int = 20):
        return await self.director_policy.observe_run(run_id, event_limit=event_limit)

    def assess(
        self,
        *,
        run_id: str,
        current_tick: int,
        agents: list[Agent],
        events: list[Event],
    ):
        return self.director_policy.assess(
            run_id=run_id,
            current_tick=current_tick,
            agents=agents,
            events=events,
        )

    async def build_director_plan(self, run_id: str, agents: list[Agent]):
        return await self.director_policy.build_director_plan(run_id, agents)

    async def persist_director_plan(self, run_id: str, plan) -> None:
        await self.director_policy.persist_director_plan(run_id, plan)

    def merge_agent_profile(self, agent: Agent, plan) -> AgentProfile:
        return self.profile_merge_policy.merge_agent_profile(agent, plan)

    def allowed_actions(self) -> list[str]:
        return self.allowed_actions_policy.allowed_actions()

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
        scenario_guidance: ScenarioGuidance | None = None,
    ):
        return self.fallback_policy.fallback_intent(
            agent_id=agent_id,
            current_location_id=current_location_id,
            home_location_id=home_location_id,
            nearby_agent_id=nearby_agent_id,
            world_role=world_role,
            current_status=current_status,
            scenario_state=scenario_state,
            scenario_guidance=scenario_guidance,
        )

    async def seed_demo_run(self, run: SimulationRun) -> None:
        if self.seed_builder is None:
            msg = "BundleWorldScenario.seed_demo_run requires a database session"
            raise RuntimeError(msg)
        await self.seed_builder.seed_demo_run(run)

    async def update_state_from_events(self, run_id: str, events: list[Event]) -> None:
        if not self.subject_alert_tracking_enabled:
            return
        if self.state_updater is None:
            msg = "BundleWorldScenario.update_state_from_events requires a database session"
            raise RuntimeError(msg)
        await self.state_updater.persist_subject_alert(run_id, events)
