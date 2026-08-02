"""Persistence logic for simulation ticks.

This module handles persisting agent locations, events, memories, and relationships
after each simulation tick.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from app.sim.economic_persistence import EconomicPersistence
from app.sim.event_utils import build_event
from app.sim.governance_persistence import GovernancePersistence
from app.sim.memory_persistence import MemoryPersistence
from app.sim.relationship_persistence import RelationshipPersistence
from app.sim.runner import TickResult
from app.sim.world import WorldState
from app.store.models import Event
from app.store.repositories import (
    AgentRepository,
    EventRepository,
    LocationRepository,
    RunRepository,
)

if TYPE_CHECKING:
    from app.store.models import Agent


class PersistenceManager:
    """Manages persistence of simulation tick results.

    This class is responsible for:
    - Persisting agent locations after movement
    - Creating and storing events (accepted and rejected)
    - Building and storing memories from events
    - Updating relationships based on interactions
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.run_repo = RunRepository(session)
        self.agent_repo = AgentRepository(session)
        self.location_repo = LocationRepository(session)
        self.event_repo = EventRepository(session)
        self.economic_persistence = EconomicPersistence(session)
        self.governance_persistence = GovernancePersistence(session)
        self.memory_persistence = MemoryPersistence(session)
        self.relationship_persistence = RelationshipPersistence(session)

    async def persist_tick_results(
        self,
        run_id: str,
        result: TickResult,
        world: WorldState,
        new_tick: int,
    ) -> list[Event]:
        """Persist all tick results including agent locations, events, memories, and relationships.

        Args:
            run_id: The simulation run ID
            result: The tick result containing accepted/rejected actions
            world: The world state after the tick
            new_tick: The new tick number

        Returns:
            List of persisted events for further processing
        """
        if self.session.in_transaction():
            return await self._persist_tick_results_in_transaction(
                run_id=run_id,
                result=result,
                world=world,
                new_tick=new_tick,
            )

        async with self.session.begin():
            return await self._persist_tick_results_in_transaction(
                run_id=run_id,
                result=result,
                world=world,
                new_tick=new_tick,
            )

    async def _persist_tick_results_in_transaction(
        self,
        *,
        run_id: str,
        result: TickResult,
        world: WorldState,
        new_tick: int,
    ) -> list[Event]:
        # Update agent locations and sync goal with schedule
        agents = await self.agent_repo.list_for_run(run_id)
        for agent in agents:
            state = world.get_agent(agent.id)
            if state is not None:
                agent.current_location_id = state.location_id
                agent.movement = state.movement.to_dict() if state.movement else {}
                agent.activity = (
                    state.activity.to_dict(world_time=world.current_time) if state.activity else {}
                )
                scheduled_goal = _compute_goal_for_schedule(world, agent)
                if scheduled_goal is not None and agent.current_goal != scheduled_goal:
                    agent.current_goal = scheduled_goal
        await self.session.flush()

        # Update tick number
        run = await self.run_repo.get(run_id)
        if run:
            await self.run_repo.set_tick(run, new_tick)

        # Build and persist events
        events = self._build_tick_events(run_id, result)
        if events:
            persisted = await self.event_repo.add_many(events)
            await self.persist_tick_governance_records(run_id, persisted)
            await self.persist_tick_governance_cases(run_id, result, world)
            await self.persist_tick_economic_state(run_id, result, world)
            await self.persist_tick_memories(run_id, persisted)
            await self.persist_tick_relationships(run_id, persisted)
            return persisted
        return []

    async def persist_tick_governance_records(self, run_id: str, events: list[Event]) -> None:
        await self.governance_persistence.persist_tick_governance_records(run_id, events)

    async def persist_tick_governance_cases(
        self,
        run_id: str,
        result: TickResult,
        world: WorldState,
    ) -> None:
        await self.governance_persistence.persist_tick_governance_cases(run_id, result, world)

    async def persist_tick_economic_state(
        self,
        run_id: str,
        result: TickResult,
        world: WorldState,
    ) -> None:
        await self.economic_persistence.persist_tick_economic_state(run_id, result, world)

    def _build_tick_events(self, run_id: str, result: TickResult) -> list[Event]:
        """Build event objects from tick results."""
        events = [
            build_event(
                run_id=run_id,
                tick_no=result.tick_no,
                world_time=result.world_time,
                action_type=item.action_type,
                payload=item.event_payload,
                accepted=True,
            )
            for item in result.accepted
        ]
        events.extend(
            build_event(
                run_id=run_id,
                tick_no=result.tick_no,
                world_time=result.world_time,
                action_type=item.action_type,
                payload={"reason": item.reason, **item.event_payload},
                accepted=False,
            )
            for item in result.rejected
        )
        return events

    async def persist_tick_memories(self, run_id: str, events: list[Event]) -> None:
        await self.memory_persistence.persist_tick_memories(run_id, events)

    async def persist_tick_memories_with_session(
        self,
        session: AsyncSession,
        run_id: str,
        events: list[Event],
    ) -> None:
        await self.memory_persistence.persist_tick_memories_with_session(session, run_id, events)

    async def persist_tick_relationships(self, run_id: str, events: list[Event]) -> None:
        await self.relationship_persistence.persist_tick_relationships(run_id, events)

    async def persist_tick_relationships_with_session(
        self,
        session: AsyncSession,
        run_id: str,
        events: list[Event],
    ) -> None:
        await self.relationship_persistence.persist_tick_relationships_with_session(
            session,
            run_id,
            events,
        )

    async def persist_agent_locations(self, run_id: str, world: WorldState) -> None:
        """Update agent locations after tick."""
        await self.set_agent_locations(run_id, world)
        await self.session.commit()

    async def set_agent_locations(self, run_id: str, world: WorldState) -> None:
        """Update agent locations without committing."""
        if not world.agents:
            return
        agents = await self.agent_repo.list_for_run(run_id)
        for agent in agents:
            state = world.get_agent(agent.id)
            if state is not None:
                agent.current_location_id = state.location_id
                agent.movement = state.movement.to_dict() if state.movement else {}
                agent.activity = (
                    state.activity.to_dict(world_time=world.current_time) if state.activity else {}
                )
        await self.session.flush()


# ─── Schedule-based goal helpers ─────────────────────────────────────────────

# Maps time-period values from WorldState._time_period() to current_plan keys
_TIME_PERIOD_TO_PLAN_KEY: dict[str, str] = {
    "dawn": "morning",
    "morning": "morning",
    "noon": "daytime",
    "afternoon": "daytime",
    "evening": "evening",
}

# Plan values that should be normalised to a concrete action goal
_PLAN_VALUE_NORMALISE: dict[str, str] = {
    "socialize": "talk",
    "prepare_day": "rest",
    "home": "go_home",
}


def _compute_goal_for_schedule(world: WorldState, agent: Agent) -> str | None:
    """Compute the agent's goal for the current time period from its daily plan.

    Returns None when no update is needed (e.g. unrecognised time period or
    empty plan), so callers can skip the write.
    """
    plan: dict = agent.current_plan or {}
    if not plan:
        return None

    time_period: str = world._time_period()

    if time_period == "night":
        # Night time: agents should be resting
        return "rest"

    plan_key = _TIME_PERIOD_TO_PLAN_KEY.get(time_period)
    if plan_key is None:
        return None

    raw_goal: str | None = plan.get(plan_key)
    if raw_goal is None:
        return None

    # Normalise plan values to recognised goal identifiers
    return _PLAN_VALUE_NORMALISE.get(raw_goal, raw_goal)
