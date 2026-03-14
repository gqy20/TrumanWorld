"""Context building logic for simulation agents.

This module handles building world context, loading world state,
and preparing context for agent decisions.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from app.scenario.truman_world.rules import load_world_config
from app.scenario.types import ScenarioGuidance, get_world_role
from app.sim.event_utils import format_event_for_context
from app.sim.runtime_context_utils import (
    build_agent_world_context,
    extract_truman_suspicion_from_agent_data,
)
from app.sim.world import AgentState, LocationState, WorldState
from app.sim.world_queries import find_nearby_agent, get_agent
from app.store.repositories import AgentRepository, EventRepository, LocationRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.store.models import Agent, Event, SimulationRun


DEFAULT_WORLD_START_TIME = datetime(2026, 3, 2, 6, 0, tzinfo=UTC)


def _load_sleep_config() -> dict:
    try:
        cfg = load_world_config()
        sleep = cfg.get("daily_rhythm", {}).get("sleep_hours", {})
        result = {}
        if "start" in sleep:
            result["sleep_start_hour"] = int(sleep["start"])
        if "end" in sleep:
            result["sleep_end_hour"] = int(sleep["end"])
        return result
    except Exception:
        return {}


class ContextBuilder:
    """Builds context for agent decisions in simulation.

    This class is responsible for:
    - Loading world state from database
    - Building agent world context for decisions
    - Extracting Truman suspicion scores
    - Finding nearby agents
    - Formatting events for context injection
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.agent_repo = AgentRepository(session)
        self.location_repo = LocationRepository(session)
        self.event_repo = EventRepository(session)

    async def load_world(self, run_id: str, run: SimulationRun, tick_minutes: int) -> WorldState:
        """Load world state from database.

        Args:
            run_id: The simulation run ID
            run: The simulation run object
            tick_minutes: Minutes per tick

        Returns:
            WorldState with locations and agents
        """
        locations, agents = await asyncio.gather(
            self.location_repo.list_for_run(run_id),
            self.agent_repo.list_for_run(run_id),
        )

        location_states = {
            location.id: LocationState(
                id=location.id,
                name=location.name,
                capacity=location.capacity,
                occupants=set(),
                location_type=location.location_type,
            )
            for location in locations
        }

        agent_states: dict[str, AgentState] = {}
        for agent in agents:
            location_id = agent.current_location_id or agent.home_location_id
            if location_id is None:
                location_id = next(iter(location_states.keys()), "unknown")

            profile = agent.profile or {}
            workplace_id = profile.get("workplace_location_id")

            agent_states[agent.id] = AgentState(
                id=agent.id,
                name=agent.name,
                location_id=location_id,
                status=agent.status or {},
                occupation=agent.occupation,
                workplace_id=workplace_id,
            )
            if location_id in location_states:
                location_states[location_id].occupants.add(agent.id)

        return WorldState(
            current_time=get_run_world_time(run),
            current_tick=run.current_tick,
            tick_minutes=tick_minutes,
            locations=location_states,
            agents=agent_states,
            world_effects=get_run_world_effects(run),
            **_load_sleep_config(),
        )

    def build_agent_world_context(
        self,
        *,
        world: WorldState,
        current_goal: str | None,
        current_location_id: str | None,
        home_location_id: str | None,
        nearby_agent_id: str | None,
        current_status: dict | None = None,
        truman_suspicion_score: float = 0.0,
        world_role: str | None = None,
        director_guidance: ScenarioGuidance | None = None,
    ) -> dict:
        """Build context dict for agent decision making.

        Args:
            world: Current world state
            current_goal: Agent's current goal
            current_location_id: Agent's current location
            home_location_id: Agent's home location
            nearby_agent_id: ID of nearby agent for interaction
            current_status: Agent's current status dict
            truman_suspicion_score: Truman's suspicion score
            world_role: Agent's role (truman/cast)
            director_guidance: Director guidance payload

        Returns:
            Context dict for agent runtime
        """
        return build_agent_world_context(
            world=world,
            current_goal=current_goal,
            current_location_id=current_location_id,
            home_location_id=home_location_id,
            nearby_agent_id=nearby_agent_id,
            current_status=current_status,
            truman_suspicion_score=truman_suspicion_score,
            world_role=world_role,
            director_guidance=director_guidance,
        )

    def find_nearby_agent(self, world: WorldState, agent_id: str, location_id: str) -> str | None:
        """Find a nearby agent at the same location.

        Args:
            world: Current world state
            agent_id: The agent looking for nearby agents
            location_id: The location to search

        Returns:
            ID of a nearby agent, or None if none found
        """
        return self._find_nearby_agent_impl(world, agent_id, location_id)

    @staticmethod
    def _find_nearby_agent_impl(world: WorldState, agent_id: str, location_id: str) -> str | None:
        """Static implementation for finding nearby agent."""
        return find_nearby_agent(world, agent_id, location_id)

    def extract_truman_suspicion_from_agent_data(
        self,
        agent_data: list[dict],
        world: WorldState,
    ) -> float:
        """Extract Truman's suspicion score from agent data.

        Args:
            agent_data: List of agent data dicts
            world: Current world state

        Returns:
            Truman's suspicion score, or 0.0 if not found
        """
        return extract_truman_suspicion_from_agent_data(agent_data, world)

    def extract_truman_suspicion_from_agents(
        self,
        agents: list[Agent],
        world: WorldState,
    ) -> float:
        """Extract Truman's suspicion score from agent objects.

        Args:
            agents: List of Agent objects
            world: Current world state

        Returns:
            Truman's suspicion score, or 0.0 if not found
        """
        for agent in agents:
            if get_world_role(agent.profile) != "truman":
                continue
            state = get_agent(world, agent.id)
            if state is None:
                continue
            return float((state.status or {}).get("suspicion_score", 0.0) or 0.0)
        return 0.0

    def format_event_for_context(
        self,
        evt: Event,
        agent_states: dict[str, AgentState],
        location_states: dict[str, LocationState],
    ) -> dict:
        return format_event_for_context(evt, agent_states, location_states)


def get_run_world_time(run: SimulationRun) -> datetime:
    """Calculate current world time from run metadata."""
    metadata = run.metadata_json or {}
    raw_start = metadata.get("world_start_time")
    if isinstance(raw_start, str):
        try:
            start_time = datetime.fromisoformat(raw_start)
        except ValueError:
            start_time = DEFAULT_WORLD_START_TIME
    else:
        start_time = DEFAULT_WORLD_START_TIME

    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=UTC)

    return start_time + timedelta(minutes=run.current_tick * run.tick_minutes)


def get_run_world_effects(run: SimulationRun) -> dict:
    metadata = run.metadata_json or {}
    world_effects = metadata.get("world_effects")
    return world_effects if isinstance(world_effects, dict) else {}
