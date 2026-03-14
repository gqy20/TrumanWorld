from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from app.director.observer import DirectorAssessment
from app.scenario.types import AgentProfile, ScenarioGuidance
from app.sim.action_resolver import ActionIntent

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.agent.runtime import AgentRuntime
    from app.director.types import DirectorPlan
    from app.store.models import Agent, Event, SimulationRun


class Scenario(ABC):
    """Abstract scenario contract for simulation orchestration."""

    @abstractmethod
    def with_session(self, session: AsyncSession | None) -> Scenario:
        raise NotImplementedError

    @abstractmethod
    def configure_runtime(self, agent_runtime: AgentRuntime) -> None:
        raise NotImplementedError

    @abstractmethod
    def configure_agent_context(self, context_builder) -> None:
        raise NotImplementedError

    @abstractmethod
    async def observe_run(self, run_id: str, event_limit: int = 20) -> DirectorAssessment:
        raise NotImplementedError

    @abstractmethod
    def assess(
        self,
        *,
        run_id: str,
        current_tick: int,
        agents: list[Agent],
        events: list[Event],
    ) -> DirectorAssessment:
        raise NotImplementedError

    @abstractmethod
    async def build_director_plan(self, run_id: str, agents: list[Agent]):
        raise NotImplementedError

    @abstractmethod
    async def persist_director_plan(self, run_id: str, plan: DirectorPlan | None) -> None:
        raise NotImplementedError

    @abstractmethod
    def merge_agent_profile(self, agent: Agent, plan) -> AgentProfile:
        raise NotImplementedError

    @abstractmethod
    def allowed_actions(self) -> list[str]:
        raise NotImplementedError

    @abstractmethod
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
    ) -> ActionIntent | None:
        raise NotImplementedError

    @abstractmethod
    async def seed_demo_run(self, run: SimulationRun) -> None:
        raise NotImplementedError

    @abstractmethod
    async def update_state_from_events(self, run_id: str, events: list[Event]) -> None:
        raise NotImplementedError
