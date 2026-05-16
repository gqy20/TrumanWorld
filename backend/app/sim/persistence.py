"""Persistence logic for simulation ticks.

This module handles persisting agent locations, events, memories, and relationships
after each simulation tick.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

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
        """Persist economic state changes and effect logs from tick results.

        Processes economic effects for all agents:
        - work_income for agents with accepted work actions
        - food decay for agents without income for N ticks
        - employment_status changes for agents with active work_ban
        """
        from app.sim.economic_state_service import EconomicStateService

        service = EconomicStateService(self.session)

        # Get all agents for this run
        agents = await self.agent_repo.list_for_run(run_id)

        # Build map of agents with accepted work actions
        accepted_work_agents: set[str] = set()
        for item in result.accepted:
            if item.action_type == "work":
                agent_id = item.event_payload.get("agent_id")
                if isinstance(agent_id, str):
                    accepted_work_agents.add(agent_id)

        # Process each agent
        for agent in agents:
            agent_id = agent.id
            tick_no = result.tick_no

            # Get associated governance case if any (for work_ban tracking)
            case_id = None

            # Process work income if agent had accepted work action
            if agent_id in accepted_work_agents:
                await service.process_work_income(
                    world=world,
                    agent_id=agent_id,
                    tick_no=tick_no,
                    run_id=run_id,
                )

            # Process daily consumption (Phase 3: economic pressure)
            await service.process_tick_consumption(
                world=world,
                agent_id=agent_id,
                tick_no=tick_no,
                run_id=run_id,
            )

            # Process tick economic effects (food decay, employment status)
            await service.process_tick_economic_effects(
                world=world,
                agent_id=agent_id,
                tick_no=tick_no,
                run_id=run_id,
                case_id=case_id,
            )

        # Process free action consequences (consequence_source == "pending")
        # These are handled by the ConsequenceGenerator in Phase 2
        await self._process_free_action_consequences(
            run_id=run_id,
            result=result,
            tick_no=result.tick_no,
        )

    async def _process_free_action_consequences(
        self,
        run_id: str,
        result: TickResult,
        tick_no: int,
    ) -> None:
        """Process free action consequences marked as pending.

        Calls the LLM ConsequenceGenerator to produce StateDelta for each
        pending free action, then applies the delta via DeltaApplier.
        """
        from app.infra.logging import get_logger
        from app.sim.consequence_generator import generate_consequences
        from app.sim.delta_applier import DeltaApplier
        from app.sim.economic_state_service import EconomicStateService

        logger = get_logger(__name__)

        # Find all accepted free actions (not standard actions)
        standard_actions = {"move", "rest", "work", "talk", "talk_rejected", "listen",
                          "conversation_started", "conversation_joined"}
        free_actions = [
            item for item in result.accepted
            if item.action_type not in standard_actions
            and item.event_payload.get("consequence_source") == "pending"
        ]

        if not free_actions:
            return

        service = EconomicStateService(self.session)
        applier = DeltaApplier(self.session)

        for item in free_actions:
            agent_id = item.event_payload.get("agent_id", "unknown")
            action_type = item.action_type
            raw_intent = item.event_payload.get("raw_intent", "")
            payload = item.event_payload.get("free_action_payload", {})
            target_agent_id = item.event_payload.get("target_agent_id")
            location_id = item.event_payload.get("location_id")
            matched_rules = ""

            # Extract matched rules if present
            if "rule_evaluation" in item.event_payload:
                rule_eval = item.event_payload.get("rule_evaluation", {})
                matched_rules = rule_eval.get("reason", "")

            # Get actor economic state
            actor_state = await service.ensure_economic_state(
                world=None, agent_id=agent_id, tick_no=tick_no, run_id=run_id
            )

            # Get target economic state if applicable
            target_state = None
            if target_agent_id:
                target_state = await service.ensure_economic_state(
                    world=None, agent_id=target_agent_id, tick_no=tick_no, run_id=run_id
                )

            # Generate consequences via LLM
            state_delta = await generate_consequences(
                action_type=action_type,
                agent_id=agent_id,
                target_agent_id=target_agent_id,
                target_location_id=location_id,
                raw_intent=raw_intent,
                payload=payload,
                actor_cash=actor_state.cash if actor_state else 0.0,
                actor_employment=actor_state.employment_status if actor_state else "unknown",
                actor_food_security=actor_state.food_security if actor_state else 1.0,
                target_cash=target_state.cash if target_state else None,
                target_employment=target_state.employment_status if target_state else None,
                target_food_security=target_state.food_security if target_state else None,
                matched_rules=matched_rules,
            )

            if state_delta is None:
                logger.warning(
                    "free_action_consequence_failed: agent=%s action=%s tick=%d",
                    agent_id,
                    action_type,
                    tick_no,
                )
                # Mark consequence source as failed
                item.event_payload["consequence_source"] = "generation_failed"
                continue

            # Apply delta via DeltaApplier
            affected = await applier.apply(
                state_delta,
                run_id=run_id,
                tick_no=tick_no,
                world=None,
            )

            # Apply relationship deltas if present
            if state_delta.relationship_deltas:
                await applier.apply_relationship_deltas(
                    state_delta,
                    run_id=run_id,
                    tick_no=tick_no,
                )

            logger.info(
                "free_action_processed: agent=%s action=%s affected=%s tick=%d",
                agent_id,
                action_type,
                affected,
                tick_no,
            )

            # Mark as successfully processed
            item.event_payload["consequence_source"] = "llm_generated"

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
        agents = await self.agent_repo.list_for_run(run_id)
        for agent in agents:
            state = world.get_agent(agent.id)
            if state is not None:
                agent.current_location_id = state.location_id
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
