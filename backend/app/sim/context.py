"""Context building logic for simulation agents.

This module handles building world context, loading world state,
and preparing context for agent decisions.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from app.scenario.bundle_registry import resolve_sleep_config_for_scenario
from app.scenario.runtime_config import ScenarioRuntimeConfig
from app.scenario.types import ScenarioGuidance, get_world_role
from app.sim.event_utils import format_event_for_context
from app.sim.runtime_context_utils import (
    build_agent_world_context,
    extract_subject_alert_from_agent_data,
)
from app.sim.world import ActiveConversationState, AgentState, LocationState, WorldState
from app.sim.world_queries import find_nearby_agent, get_agent
from app.store.repositories import AgentRepository, EventRepository, LocationRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.store.models import Agent, Event, SimulationRun


DEFAULT_WORLD_START_TIME = datetime(2026, 3, 2, 6, 0, tzinfo=UTC)


class ContextBuilder:
    """Builds context for agent decisions in simulation.

    This class is responsible for:
    - Loading world state from database
    - Building agent world context for decisions
    - Extracting primary subject alert scores
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
        from app.sim.agent_snapshot_builder import build_agent_relationship_contexts

        relationship_contexts = await build_agent_relationship_contexts(
            session=self.session,
            run_id=run_id,
            agents=list(agents),
        )
        active_conversations = await self._load_active_conversations(
            run_id=run_id,
            current_tick=run.current_tick or 0,
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
            relationship_contexts=relationship_contexts,
            active_conversations=active_conversations,
            **resolve_sleep_config_for_scenario(run.scenario_type),
        )

    async def _load_active_conversations(
        self,
        *,
        run_id: str,
        current_tick: int,
    ) -> dict[str, ActiveConversationState]:
        if current_tick <= 0:
            return {}

        recent_events, _total = await self.event_repo.list_timeline_api_rows(
            run_id=run_id,
            tick_from=current_tick,
            tick_to=current_tick,
            event_type="speech,listen,conversation_started,conversation_joined",
            limit=50,
            order_desc=False,
        )

        conversations: dict[str, ActiveConversationState] = {}
        for event in recent_events:
            payload = event.payload or {}
            conversation_id = payload.get("conversation_id")
            if not isinstance(conversation_id, str) or not conversation_id:
                continue
            participant_ids = payload.get("participant_ids")
            if not isinstance(participant_ids, list):
                continue
            normalized_participants = [pid for pid in participant_ids if isinstance(pid, str)]
            if len(normalized_participants) < 2:
                continue

            speaker_agent_id = payload.get("speaker_agent_id")
            if not isinstance(speaker_agent_id, str) or not speaker_agent_id:
                speaker_agent_id = event.actor_agent_id
            if not isinstance(speaker_agent_id, str) or not speaker_agent_id:
                continue

            existing = conversations.get(conversation_id)
            if existing is None:
                conversations[conversation_id] = ActiveConversationState(
                    id=conversation_id,
                    location_id=event.location_id or "",
                    participant_ids=normalized_participants,
                    active_speaker_id=speaker_agent_id,
                    last_tick_no=event.tick_no,
                )
                continue

            existing.location_id = event.location_id or existing.location_id
            existing.participant_ids = normalized_participants
            existing.active_speaker_id = speaker_agent_id
            existing.last_tick_no = max(existing.last_tick_no, event.tick_no)

        return {cid: conv for cid, conv in conversations.items() if conv.location_id}

    def build_agent_world_context(
        self,
        *,
        world: WorldState,
        current_goal: str | None,
        current_location_id: str | None,
        home_location_id: str | None,
        nearby_agent_id: str | None,
        current_status: dict | None = None,
        subject_alert_score: float | None = 0.0,
        world_role: str | None = None,
        director_guidance: ScenarioGuidance | None = None,
        relationship_context: dict[str, dict[str, object]] | None = None,
        recent_events: list[dict] | None = None,
    ) -> dict:
        """Build context dict for agent decision making.

        Args:
            world: Current world state
            current_goal: Agent's current goal
            current_location_id: Agent's current location
            home_location_id: Agent's home location
            nearby_agent_id: ID of nearby agent for interaction
            current_status: Agent's current status dict
            subject_alert_score: Primary subject alert score when enabled
            world_role: Agent's scenario role
            director_guidance: Director guidance payload

        Returns:
            Context dict for agent runtime
        """
        return build_agent_world_context(
            agent_id=None,
            world=world,
            current_goal=current_goal,
            current_location_id=current_location_id,
            home_location_id=home_location_id,
            nearby_agent_id=nearby_agent_id,
            current_status=current_status,
            subject_alert_score=subject_alert_score,
            world_role=world_role,
            director_guidance=director_guidance,
            relationship_context=relationship_context,
            recent_events=recent_events,
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

    def extract_subject_alert_from_agent_data(
        self,
        agent_data: list[dict],
        world: WorldState,
        *,
        semantics: ScenarioRuntimeConfig | None = None,
    ) -> float:
        """Extract the primary subject alert score from agent data."""
        return extract_subject_alert_from_agent_data(agent_data, world, semantics=semantics)

    def extract_subject_alert_from_agents(
        self,
        agents: list[Agent],
        world: WorldState,
        *,
        semantics: ScenarioRuntimeConfig | None = None,
    ) -> float:
        """Extract the primary subject alert score from agent objects."""
        resolved = semantics or ScenarioRuntimeConfig()
        for agent in agents:
            if get_world_role(agent.profile) != resolved.subject_role:
                continue
            state = get_agent(world, agent.id)
            if state is None:
                continue
            return float((state.status or {}).get(resolved.alert_metric, 0.0) or 0.0)
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
