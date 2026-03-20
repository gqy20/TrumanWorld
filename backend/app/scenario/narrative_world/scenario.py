from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from app.agent.context_builder import ScenarioContextHooks
from app.scenario.base import Scenario
from app.scenario.bundle_registry import get_scenario_bundle
from app.scenario.narrative_world.coordinator import NarrativeWorldCoordinator
from app.scenario.narrative_world.rules import (
    build_role_context,
    build_scene_guidance,
    build_world_common_knowledge,
    filter_world_for_role,
)
from app.scenario.narrative_world.seed import NarrativeWorldSeedBuilder
from app.scenario.narrative_world.state import (
    NarrativeWorldStateUpdater,
    build_alert_state_semantics,
)
from app.scenario.runtime_config import build_scenario_runtime_config
from app.scenario.types import AgentProfile, ScenarioGuidance

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.agent.runtime import AgentRuntime
    from app.store.models import Agent, Event, SimulationRun


class NarrativeWorldScenario(Scenario):
    """Scenario implementation for the narrative-world adapter."""

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
        self.runtime_config = build_scenario_runtime_config(scenario_id)
        self.subject_alert_tracking_enabled = (
            capabilities.subject_alert_tracking
            if capabilities is not None and capabilities.subject_alert_tracking is not None
            else True
        )
        self.coordinator = NarrativeWorldCoordinator(session, scenario_id=scenario_id)
        self.state_updater = (
            NarrativeWorldStateUpdater(
                session,
                semantics=build_alert_state_semantics(scenario_id),
            )
            if session is not None and self.subject_alert_tracking_enabled
            else None
        )
        self.seed_builder = (
            NarrativeWorldSeedBuilder(session, scenario_id=scenario_id)
            if session is not None
            else None
        )

    def with_session(self, session: AsyncSession | None) -> NarrativeWorldScenario:
        return NarrativeWorldScenario(session, scenario_id=self.scenario_id)

    def configure_runtime(self, agent_runtime: AgentRuntime) -> None:
        agent_runtime.configure_allowed_actions(self.allowed_actions())
        self.coordinator.configure_runtime(agent_runtime)
        self.configure_agent_context(agent_runtime.context_builder)

    def configure_agent_context(self, context_builder) -> None:
        context_builder.configure_policy(
            ScenarioContextHooks(
                world_filter_hook=partial(filter_world_for_role, semantics=self.runtime_config),
                role_context_hook=partial(build_role_context, semantics=self.runtime_config),
                scene_guidance_hook=partial(build_scene_guidance, semantics=self.runtime_config),
                world_knowledge_hook=partial(build_world_common_knowledge, self.scenario_id),
            )
        )

    async def observe_run(self, run_id: str, event_limit: int = 20):
        return await self.coordinator.observe_run(run_id, event_limit=event_limit)

    def assess(
        self,
        *,
        run_id: str,
        current_tick: int,
        agents: list[Agent],
        events: list[Event],
    ):
        return self.coordinator.assess(
            run_id=run_id,
            current_tick=current_tick,
            agents=agents,
            events=events,
        )

    async def build_director_plan(self, run_id: str, agents: list[Agent]):
        return await self.coordinator.build_director_plan(run_id, agents)

    async def persist_director_plan(self, run_id: str, plan) -> None:
        """Persist the director plan generated in Phase 1 (must be called in write_session)."""
        await self.coordinator.persist_director_plan(run_id, plan)

    def merge_agent_profile(self, agent: Agent, plan) -> AgentProfile:
        return self.coordinator.merge_agent_profile(agent, plan)

    def allowed_actions(self) -> list[str]:
        return ["move", "talk", "work", "rest"]

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
        return self.coordinator.fallback_intent(
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
            msg = "NarrativeWorldScenario.seed_demo_run requires a database session"
            raise RuntimeError(msg)
        await self.seed_builder.seed_demo_run(run)

    async def update_state_from_events(self, run_id: str, events: list[Event]) -> None:
        if not self.subject_alert_tracking_enabled:
            return
        if self.state_updater is None:
            msg = "NarrativeWorldScenario.update_state_from_events requires a database session"
            raise RuntimeError(msg)
        await self.state_updater.persist_subject_alert(run_id, events)
