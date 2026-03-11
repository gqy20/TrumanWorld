"""Persistence logic for simulation ticks.

This module handles persisting agent locations, events, memories, and relationships
after each simulation tick.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.sim.event_utils import build_event
from app.sim.memory_constants import calculate_memory_importance, determine_memory_category
from app.sim.runner import TickResult
from app.sim.world import WorldState
from app.store.repositories import (
    AgentRepository,
    EventRepository,
    LocationRepository,
    MemoryRepository,
    RelationshipRepository,
    RunRepository,
)
from app.store.models import Event, Memory

if TYPE_CHECKING:
    from app.store.models import Agent


ROUTINE_MEMORY_EVENT_TYPES = {"work", "rest"}
ROUTINE_MEMORY_LOOKBACK_TICKS = 3


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
        self.memory_repo = MemoryRepository(session)
        self.relationship_repo = RelationshipRepository(session)

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
        # Update agent locations and sync goal with schedule
        agents = await self.agent_repo.list_for_run(run_id)
        for agent in agents:
            state = world.get_agent(agent.id)
            if state is not None:
                agent.current_location_id = state.location_id
                scheduled_goal = _compute_goal_for_schedule(world, agent)
                if scheduled_goal is not None and agent.current_goal != scheduled_goal:
                    agent.current_goal = scheduled_goal
        await self.session.commit()

        # Update tick number
        run = await self.run_repo.get(run_id)
        if run:
            await self.run_repo.update_tick(run, new_tick)

        # Build and persist events
        events = self._build_tick_events(run_id, result)
        if events:
            persisted = await self.event_repo.create_many(events)
            await self.persist_tick_memories(run_id, persisted)
            await self.persist_tick_relationships(run_id, persisted)
            return persisted
        return []

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
        """Persist memories from tick events."""
        agents_list, locations_list = await asyncio.gather(
            self.agent_repo.list_for_run(run_id),
            self.location_repo.list_for_run(run_id),
        )
        agent_map = {a.id: a for a in agents_list}
        agent_name_map = {a.id: a.name for a in agents_list}
        location_name_map = {loc.id: loc.name for loc in locations_list}
        memories: list[Memory] = []
        updated_routine_memory = False
        for event in events:
            if event.event_type.endswith("_rejected") or event.actor_agent_id is None:
                continue

            for agent_id, content, summary, related_agent_id in self._build_memory_records(
                event, agent_name_map, location_name_map
            ):
                routine_memory = await self._find_routine_memory_to_extend(
                    run_id=run_id,
                    agent_id=agent_id,
                    event=event,
                    summary=summary,
                )
                if routine_memory is not None:
                    self._extend_routine_memory(routine_memory, event)
                    updated_routine_memory = True
                    continue
                perspective = self._determine_perspective(event, agent_id)
                relationship_strength = await self._relationship_strength(
                    run_id=run_id,
                    agent_id=agent_id,
                    related_agent_id=related_agent_id,
                )
                memory_importance = calculate_memory_importance(
                    event_importance=event.importance,
                    perspective=perspective,
                    relationship_strength=relationship_strength,
                    goal_relevance=self._is_goal_relevant(event, agent_map.get(agent_id)),
                    location_relevance=self._is_location_relevant(event, agent_map.get(agent_id)),
                )
                memory_category = determine_memory_category(
                    importance=memory_importance,
                    tick_age=0,  # New memory, age is 0
                )

                memories.append(
                    Memory(
                        id=str(uuid4()),
                        run_id=run_id,
                        agent_id=agent_id,
                        tick_no=event.tick_no,
                        memory_type="episodic_short",
                        memory_category=memory_category,
                        content=content,
                        summary=summary,
                        importance=memory_importance,
                        event_importance=event.importance,
                        self_relevance=self._perspective_relevance(perspective),
                        streak_count=1,
                        last_tick_no=event.tick_no,
                        related_agent_id=related_agent_id,
                        location_id=event.location_id,
                        source_event_id=event.id,
                        metadata_json={"event_type": event.event_type},
                    )
                )

        if memories:
            await self.memory_repo.create_many(memories)
        elif updated_routine_memory:
            await self.session.commit()

    async def persist_tick_memories_with_session(
        self,
        session: AsyncSession,
        run_id: str,
        events: list[Event],
    ) -> None:
        """Persist memories using a provided session (for isolated tick operations)."""
        agent_repo = AgentRepository(session)
        location_repo = LocationRepository(session)
        agents, locations = await asyncio.gather(
            agent_repo.list_for_run(run_id),
            location_repo.list_for_run(run_id),
        )
        rel_repo = RelationshipRepository(session)
        agent_map = {a.id: a for a in agents}
        agent_name_map = {a.id: a.name for a in agents}
        location_name_map = {loc.id: loc.name for loc in locations}
        memories: list[Memory] = []
        updated_routine_memory = False
        for event in events:
            if event.event_type.endswith("_rejected") or event.actor_agent_id is None:
                continue

            for agent_id, content, summary, related_agent_id in self._build_memory_records(
                event, agent_name_map, location_name_map
            ):
                routine_memory = await self._find_routine_memory_to_extend_with_session(
                    session=session,
                    run_id=run_id,
                    agent_id=agent_id,
                    event=event,
                    summary=summary,
                )
                if routine_memory is not None:
                    self._extend_routine_memory(routine_memory, event)
                    updated_routine_memory = True
                    continue
                perspective = self._determine_perspective(event, agent_id)
                relationship_strength = await self._relationship_strength_with_repo(
                    rel_repo=rel_repo,
                    run_id=run_id,
                    agent_id=agent_id,
                    related_agent_id=related_agent_id,
                )
                memory_importance = calculate_memory_importance(
                    event_importance=event.importance,
                    perspective=perspective,
                    relationship_strength=relationship_strength,
                    goal_relevance=self._is_goal_relevant(event, agent_map.get(agent_id)),
                    location_relevance=self._is_location_relevant(event, agent_map.get(agent_id)),
                )
                memory_category = determine_memory_category(
                    importance=memory_importance,
                    tick_age=0,  # New memory, age is 0
                )

                memories.append(
                    Memory(
                        id=str(uuid4()),
                        run_id=run_id,
                        agent_id=agent_id,
                        tick_no=event.tick_no,
                        memory_type="episodic_short",
                        memory_category=memory_category,
                        content=content,
                        summary=summary,
                        importance=memory_importance,
                        event_importance=event.importance,
                        self_relevance=self._perspective_relevance(perspective),
                        streak_count=1,
                        last_tick_no=event.tick_no,
                        related_agent_id=related_agent_id,
                        location_id=event.location_id,
                        source_event_id=event.id,
                        metadata_json={"event_type": event.event_type},
                    )
                )

        if memories:
            memory_repo = MemoryRepository(session)
            await memory_repo.create_many(memories)
        elif updated_routine_memory:
            await session.commit()

    async def persist_tick_relationships(self, run_id: str, events: list[Event]) -> None:
        """Persist relationships from talk events."""
        for event in events:
            if event.event_type != "talk":
                continue
            if event.actor_agent_id is None or event.target_agent_id is None:
                continue

            await self.relationship_repo.upsert_interaction(
                run_id=run_id,
                agent_id=event.actor_agent_id,
                other_agent_id=event.target_agent_id,
                familiarity_delta=0.1,
                trust_delta=0.05,
                affinity_delta=0.05,
            )
            await self.relationship_repo.upsert_interaction(
                run_id=run_id,
                agent_id=event.target_agent_id,
                other_agent_id=event.actor_agent_id,
                familiarity_delta=0.1,
                trust_delta=0.05,
                affinity_delta=0.05,
            )

    async def persist_tick_relationships_with_session(
        self,
        session: AsyncSession,
        run_id: str,
        events: list[Event],
    ) -> None:
        """Persist relationships using a provided session."""
        rel_repo = RelationshipRepository(session)
        for event in events:
            if event.event_type != "talk":
                continue
            if event.actor_agent_id is None or event.target_agent_id is None:
                continue

            await rel_repo.upsert_interaction(
                run_id=run_id,
                agent_id=event.actor_agent_id,
                other_agent_id=event.target_agent_id,
                familiarity_delta=0.1,
                trust_delta=0.05,
                affinity_delta=0.05,
            )
            await rel_repo.upsert_interaction(
                run_id=run_id,
                agent_id=event.target_agent_id,
                other_agent_id=event.actor_agent_id,
                familiarity_delta=0.1,
                trust_delta=0.05,
                affinity_delta=0.05,
            )

    async def persist_agent_locations(self, run_id: str, world: WorldState) -> None:
        """Update agent locations after tick."""
        agents = await self.agent_repo.list_for_run(run_id)
        for agent in agents:
            state = world.get_agent(agent.id)
            if state is not None:
                agent.current_location_id = state.location_id
        await self.session.commit()

    def _build_memory_records(
        self,
        event: Event,
        agent_name_map: dict[str, str] | None = None,
        location_name_map: dict[str, str] | None = None,
    ) -> list[tuple[str, str, str, str | None]]:
        """Build memory records from an event.

        Returns list of tuples: (agent_id, content, summary, related_agent_id)
        """
        payload = event.payload or {}
        _agents = agent_name_map or {}
        _locations = location_name_map or {}

        def agent_name(agent_id: str | None) -> str:
            if not agent_id:
                return "someone"
            return _agents.get(agent_id, agent_id)

        def location_name(loc_id: str | None) -> str:
            if not loc_id:
                return "unknown"
            return _locations.get(loc_id, loc_id)

        if event.event_type == "move":
            destination = location_name(str(payload.get("to_location_id", "")) or None)
            origin = location_name(str(payload.get("from_location_id", "")) or None)
            return [
                (
                    event.actor_agent_id,
                    f"Moved from {origin} to {destination}.",
                    f"Moved to {destination}",
                    None,
                )
            ]

        if event.event_type == "talk":
            target_id = str(payload.get("target_agent_id") or event.target_agent_id or "")
            loc_id = str(payload.get("location_id") or "")
            target = agent_name(target_id)
            actor = agent_name(event.actor_agent_id)
            loc = location_name(loc_id)
            message = payload.get("message", "")

            if message:
                actor_content = f'Talked with {target} at {loc}: "{message}"'
                actor_summary = (
                    f"Talked with {target}: {message[:30]}{'...' if len(message) > 30 else ''}"
                )
                target_content = f'{actor} said: "{message}"'
                target_summary = f"{actor} said: {message[:30]}{'...' if len(message) > 30 else ''}"
            else:
                actor_content = f"Talked with {target} at {loc}."
                actor_summary = f"Talked with {target}"
                target_content = f"Talked with {actor} at {loc}."
                target_summary = f"Talked with {actor}"

            records: list[tuple[str, str, str, str | None]] = [
                (event.actor_agent_id, actor_content, actor_summary, event.target_agent_id)
            ]
            if event.target_agent_id:
                records.append(
                    (event.target_agent_id, target_content, target_summary, event.actor_agent_id)
                )
            return records

        if event.event_type == "work":
            return [(event.actor_agent_id, "Worked during this tick.", "Worked", None)]

        if event.event_type == "rest":
            return [(event.actor_agent_id, "Rested during this tick.", "Rested", None)]

        return [
            (
                event.actor_agent_id,
                f"Experienced event {event.event_type}.",
                f"Event: {event.event_type}",
                event.target_agent_id,
            )
        ]

    @staticmethod
    def _determine_perspective(event: Event, agent_id: str) -> str:
        if agent_id == event.actor_agent_id:
            return "actor"
        if agent_id == event.target_agent_id:
            return "target"
        return "observer"

    @staticmethod
    def _perspective_relevance(perspective: str) -> float:
        if perspective == "target":
            return 1.0
        if perspective == "actor":
            return 0.8
        return 0.4

    @staticmethod
    def _is_goal_relevant(event: Event, agent: "Agent | None") -> bool:
        if agent is None or not agent.current_goal:
            return False
        goal = agent.current_goal.lower()
        if event.event_type in goal:
            return True
        return event.event_type == "move" and goal.startswith("move:")

    @staticmethod
    def _is_location_relevant(event: Event, agent: "Agent | None") -> bool:
        if agent is None:
            return False
        return bool(
            event.location_id
            and (event.location_id == agent.current_location_id or event.location_id == agent.home_location_id)
        )

    async def _relationship_strength(
        self,
        *,
        run_id: str,
        agent_id: str,
        related_agent_id: str | None,
    ) -> float:
        return await self._relationship_strength_with_repo(
            rel_repo=self.relationship_repo,
            run_id=run_id,
            agent_id=agent_id,
            related_agent_id=related_agent_id,
        )

    async def _relationship_strength_with_repo(
        self,
        *,
        rel_repo: RelationshipRepository,
        run_id: str,
        agent_id: str,
        related_agent_id: str | None,
    ) -> float:
        if not related_agent_id:
            return 0.0
        relation = await rel_repo.get_pair(run_id, agent_id, related_agent_id)
        if relation is None:
            return 0.0
        components = [relation.familiarity, max(relation.trust, 0.0), max(relation.affinity, 0.0)]
        return sum(components) / len(components)

    async def _find_routine_memory_to_extend(
        self,
        *,
        run_id: str,
        agent_id: str,
        event: Event,
        summary: str,
    ) -> Memory | None:
        return await self._find_routine_memory_to_extend_with_session(
            session=self.session,
            run_id=run_id,
            agent_id=agent_id,
            event=event,
            summary=summary,
        )

    async def _find_routine_memory_to_extend_with_session(
        self,
        *,
        session: AsyncSession,
        run_id: str,
        agent_id: str,
        event: Event,
        summary: str,
    ) -> Memory | None:
        if event.event_type not in ROUTINE_MEMORY_EVENT_TYPES:
            return None
        return await MemoryRepository(session).find_recent_routine_memory(
            run_id=run_id,
            agent_id=agent_id,
            summary=summary,
            location_id=event.location_id,
            since_tick=max(0, event.tick_no - ROUTINE_MEMORY_LOOKBACK_TICKS),
        )

    @staticmethod
    def _extend_routine_memory(memory: Memory, event: Event) -> None:
        next_streak = (memory.streak_count or 1) + 1
        memory.streak_count = next_streak
        memory.last_tick_no = event.tick_no
        memory.tick_no = event.tick_no
        if next_streak >= 3:
            memory.memory_category = "medium_term"
        if memory.summary == "Worked":
            memory.content = f"Worked during {next_streak} consecutive ticks."
        elif memory.summary == "Rested":
            memory.content = f"Rested during {next_streak} consecutive ticks."


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


def _compute_goal_for_schedule(world: "WorldState", agent: "Agent") -> str | None:
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
