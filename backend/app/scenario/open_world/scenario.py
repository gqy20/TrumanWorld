from __future__ import annotations

from typing import TYPE_CHECKING

from app.director.observer import DirectorAssessment
from app.scenario.base import Scenario
from app.sim.action_resolver import ActionIntent
from app.store.models import Agent, Location

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.store.models import Event, SimulationRun


class OpenWorldScenario(Scenario):
    """A minimal low-constraint scenario used as a second scenario example."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        self.session = session

    def with_session(self, session: AsyncSession | None) -> "OpenWorldScenario":
        return OpenWorldScenario(session)

    def configure_runtime(self, agent_runtime) -> None:
        return None

    def configure_agent_context(self, context_builder) -> None:
        context_builder.configure_hooks()

    async def observe_run(self, run_id: str, event_limit: int = 20) -> DirectorAssessment:
        return DirectorAssessment(
            run_id=run_id,
            current_tick=0,
            truman_agent_id=None,
            truman_suspicion_score=0.0,
            suspicion_level="low",
            continuity_risk="stable",
            focus_agent_ids=[],
            notes=["OpenWorldScenario 不使用导演观察。"],
        )

    def assess(
        self,
        *,
        run_id: str,
        current_tick: int,
        agents: list[Agent],
        events: list[Event],
    ) -> DirectorAssessment:
        return DirectorAssessment(
            run_id=run_id,
            current_tick=current_tick,
            truman_agent_id=None,
            truman_suspicion_score=0.0,
            suspicion_level="low",
            continuity_risk="stable",
            focus_agent_ids=[agent.id for agent in agents[:1]],
            notes=["OpenWorldScenario 保持最小叙事约束。"],
        )

    async def build_director_plan(self, run_id: str, agents: list[Agent]):
        return None

    def merge_agent_profile(self, agent: Agent, plan) -> dict:
        return dict(agent.profile or {})

    def fallback_intent(
        self,
        *,
        agent_id: str,
        current_location_id: str,
        home_location_id: str | None,
        nearby_agent_id: str | None,
        world_role: str | None = None,
        current_status: dict | None = None,
        truman_suspicion_score: float = 0.0,
        director_scene_goal: str | None = None,
        director_priority: str | None = None,
    ) -> ActionIntent | None:
        return None

    async def seed_demo_run(self, run: SimulationRun) -> None:
        if self.session is None:
            msg = "OpenWorldScenario.seed_demo_run requires a database session"
            raise RuntimeError(msg)

        meadow = Location(
            id=f"{run.id}-meadow",
            run_id=run.id,
            name="Open Meadow",
            location_type="field",
            capacity=8,
            x=0,
            y=0,
            attributes={"kind": "open"},
        )
        rover = Agent(
            id=f"{run.id}-rover",
            run_id=run.id,
            name="Rover",
            occupation="wanderer",
            home_location_id=meadow.id,
            current_location_id=meadow.id,
            current_goal="rest",
            personality={"openness": 0.8},
            profile={"agent_config_id": "neighbor", "world_role": "npc"},
            status={"energy": 0.9},
            current_plan={"daytime": "wander"},
        )

        self.session.add(meadow)
        await self.session.flush()
        self.session.add(rover)
        await self.session.commit()

    async def update_state_from_events(self, run_id: str, events: list[Event]) -> None:
        return None
