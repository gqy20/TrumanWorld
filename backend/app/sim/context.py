"""Context building logic for simulation agents.

This module handles building world context, loading world state,
and preparing context for agent decisions.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from app.scenario.bundle_registry import resolve_sleep_config_for_scenario
from app.scenario.embodiment_config import (
    load_embodiment_catalog_for_scenario,
    load_social_spatial_config_for_scenario,
)
from app.scenario.spatial_manifest import load_world_map_manifest_for_scenario
from app.scenario.runtime_config import ScenarioRuntimeConfig
from app.scenario.types import ScenarioGuidance, get_world_role
from app.sim.event_utils import format_event_for_context
from app.sim.movement import AgentMovementState
from app.sim.activity import ActivityInstance
from app.sim.runtime_context_utils import (
    build_agent_world_context,
    extract_subject_alert_from_agent_data,
)
from app.sim.world import ActiveConversationState, AgentState, LocationState, WorldState
from app.sim.world_map import build_authoritative_world_map
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
        locations = await self.location_repo.list_for_run(run_id)
        agents = await self.agent_repo.list_for_run(run_id)
        from app.sim.agent_snapshot_builder import build_agent_relationship_contexts

        relationship_contexts = await build_agent_relationship_contexts(
            session=self.session,
            run_id=run_id,
            agents=list(agents),
        )
        active_conversations = await load_active_conversations(
            event_repo=self.event_repo,
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
                x=location.x,
                y=location.y,
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

            movement = AgentMovementState.from_dict(agent.movement)
            activity = ActivityInstance.from_dict(agent.activity)
            agent_states[agent.id] = AgentState(
                id=agent.id,
                name=agent.name,
                location_id=location_id,
                status=agent.status or {},
                occupation=agent.occupation,
                workplace_id=workplace_id,
                movement=movement,
                activity=activity,
            )
            if movement is None and location_id in location_states:
                location_states[location_id].occupants.add(agent.id)

        spatial_manifest = load_world_map_manifest_for_scenario(run.scenario_type)
        return WorldState(
            current_time=get_run_world_time(run),
            current_tick=run.current_tick,
            tick_minutes=tick_minutes,
            locations=location_states,
            agents=agent_states,
            world_effects=get_run_world_effects(run),
            relationship_contexts=relationship_contexts,
            active_conversations=active_conversations,
            topology=build_authoritative_world_map(
                locations,
                scenario_id=run.scenario_type,
                run_id=run_id,
            ),
            embodiment_catalog=load_embodiment_catalog_for_scenario(run.scenario_type),
            world_seed=run.world_seed or 0,
            social_spatial_config=load_social_spatial_config_for_scenario(run.scenario_type),
            location_zone_ids={
                f"{run_id}-{zone.location_id}": zone.id
                for zone in (spatial_manifest.zones if spatial_manifest else [])
            },
            **resolve_sleep_config_for_scenario(run.scenario_type),
        )

    async def _load_active_conversations(
        self,
        *,
        run_id: str,
        current_tick: int,
    ) -> dict[str, ActiveConversationState]:
        return await load_active_conversations(
            event_repo=self.event_repo,
            run_id=run_id,
            current_tick=current_tick,
        )

    @staticmethod
    def _repeat_count(history: list[tuple[int, str, str]]) -> int:
        return _repeat_count(history)

    @staticmethod
    def _normalize_conversation_text(text: str) -> str:
        return _normalize_conversation_text(text)

    @staticmethod
    def _looks_like_question(message: str) -> bool:
        return _looks_like_question(message)

    @staticmethod
    def _looks_like_proposal_or_question(message: str) -> bool:
        return _looks_like_proposal_or_question(message)

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
        workplace_location_id: str | None = None,
        relationship_context: dict[str, dict[str, object]] | None = None,
        recent_events: list[dict] | None = None,
    ) -> dict:
        """Build context dict for agent decision making."""
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
            workplace_location_id=workplace_location_id,
            relationship_context=relationship_context,
            recent_events=recent_events,
        )

    def find_nearby_agent(self, world: WorldState, agent_id: str, location_id: str) -> str | None:
        """Find a nearby agent at the same location."""
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


async def load_active_conversations(
    *,
    event_repo: EventRepository,
    run_id: str,
    current_tick: int,
) -> dict[str, ActiveConversationState]:
    if current_tick <= 0:
        return {}

    recent_events, _total = await event_repo.list_timeline_api_rows(
        run_id=run_id,
        tick_from=max(0, current_tick - 12),
        tick_to=current_tick,
        event_type=("speech,listen,conversation_started,conversation_joined,conversation_closed"),
        limit=300,
        order_desc=False,
    )

    speech_history: dict[str, list[tuple[int, str, str]]] = {}
    conversations: dict[str, ActiveConversationState] = {}
    closed_conversation_ids: set[str] = set()
    for event in recent_events:
        payload = event.payload or {}
        conversation_id = payload.get("conversation_id")
        if not isinstance(conversation_id, str) or not conversation_id:
            continue
        if event.event_type == "conversation_closed":
            closed_conversation_ids.add(conversation_id)
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

        message = payload.get("message")
        if isinstance(message, str) and message.strip() and event.event_type == "speech":
            speech_history.setdefault(conversation_id, []).append(
                (event.tick_no, speaker_agent_id, message.strip())
            )

        existing = conversations.get(conversation_id)
        if existing is None:
            conversations[conversation_id] = ActiveConversationState(
                id=conversation_id,
                location_id=event.location_id or "",
                participant_ids=normalized_participants,
                active_speaker_id=speaker_agent_id,
                last_tick_no=event.tick_no,
                started_tick_no=event.tick_no,
            )
            continue

        existing.location_id = event.location_id or existing.location_id
        existing.participant_ids = normalized_participants
        existing.active_speaker_id = speaker_agent_id
        existing.last_tick_no = max(existing.last_tick_no, event.tick_no)
        existing.started_tick_no = min(existing.started_tick_no, event.tick_no)

    for conversation_id, conversation in conversations.items():
        history = speech_history.get(conversation_id, [])
        if not history:
            continue
        history.sort(key=lambda item: item[0], reverse=True)
        _tick_no, _speaker_id, latest_message = history[0]
        conversation.last_message_summary = latest_message
        if _looks_like_proposal_or_question(latest_message):
            conversation.last_proposal = latest_message
        if _looks_like_question(latest_message):
            conversation.open_question = latest_message
        conversation.repeat_count = _repeat_count(history)
        conversation.turn_count = len(history)
        conversation.phase = "closing" if len(history) >= 6 else "open"

    return {
        cid: conv
        for cid, conv in conversations.items()
        if conv.location_id and cid not in closed_conversation_ids
    }


def _repeat_count(history: list[tuple[int, str, str]]) -> int:
    if not history:
        return 0
    _tick_no, speaker_id, latest_message = history[0]
    normalized_latest = _normalize_conversation_text(latest_message)
    count = 0
    for _tick_no, current_speaker_id, message in history:
        if current_speaker_id != speaker_id:
            break
        if _normalize_conversation_text(message) != normalized_latest:
            break
        count += 1
    return count


def _normalize_conversation_text(text: str) -> str:
    return "".join(text.split()).strip("，。！？,.!?：:;；\"'“”‘’").lower()


def _looks_like_question(message: str) -> bool:
    return any(token in message for token in ("？", "?", "要不要", "可以吗", "方便吗", "吗"))


def _looks_like_proposal_or_question(message: str) -> bool:
    return _looks_like_question(message) or any(
        token in message for token in ("一起", "先花十分钟", "要不", "不如")
    )


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
