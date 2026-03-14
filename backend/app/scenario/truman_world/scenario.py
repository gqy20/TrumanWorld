from __future__ import annotations

from typing import TYPE_CHECKING

from app.agent.context_builder import ScenarioContextHooks
from app.scenario.base import Scenario
from app.scenario.truman_world.coordinator import TrumanWorldCoordinator
from app.scenario.truman_world.rules import (
    build_role_context,
    build_scene_guidance,
    build_world_common_knowledge,
    filter_world_for_role,
)
from app.scenario.truman_world.seed import TrumanWorldSeedBuilder
from app.scenario.truman_world.state import TrumanWorldStateUpdater
from app.scenario.types import AgentProfile, ScenarioGuidance

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.agent.runtime import AgentRuntime
    from app.store.models import Agent, Event, SimulationRun


class TrumanWorldScenario(Scenario):
    """Scenario implementation for the Truman world."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        self.session = session
        self.coordinator = TrumanWorldCoordinator(session)
        self.state_updater = TrumanWorldStateUpdater(session) if session is not None else None
        self.seed_builder = TrumanWorldSeedBuilder(session) if session is not None else None

    def with_session(self, session: AsyncSession | None) -> TrumanWorldScenario:
        return TrumanWorldScenario(session)

    def configure_runtime(self, agent_runtime: AgentRuntime) -> None:
        agent_runtime.configure_allowed_actions(self.allowed_actions())
        self.coordinator.configure_runtime(agent_runtime)
        self.configure_agent_context(agent_runtime.context_builder)

    def configure_agent_context(self, context_builder) -> None:
        context_builder.configure_policy(
            ScenarioContextHooks(
                world_filter_hook=filter_world_for_role,
                role_context_hook=build_role_context,
                scene_guidance_hook=build_scene_guidance,
                world_knowledge_hook=build_world_common_knowledge,
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
            msg = "TrumanWorldScenario.seed_demo_run requires a database session"
            raise RuntimeError(msg)
        await self.seed_builder.seed_demo_run(run)

    async def update_state_from_events(self, run_id: str, events: list[Event]) -> None:
        if self.state_updater is None:
            msg = "TrumanWorldScenario.update_state_from_events requires a database session"
            raise RuntimeError(msg)
        await self.state_updater.persist_truman_suspicion(run_id, events)
