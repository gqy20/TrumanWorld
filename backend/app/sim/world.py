from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from typing import Any

from app.sim.movement import AgentMovementState, create_agent_movement
from app.sim.world_map import build_world_map


@dataclass
class LocationState:
    id: str
    name: str
    capacity: int = 10
    occupants: set[str] = field(default_factory=set)
    location_type: str | None = None
    x: int | None = None
    y: int | None = None


@dataclass
class AgentState:
    id: str
    name: str
    location_id: str
    status: dict[str, Any] = field(default_factory=dict)
    occupation: str | None = None
    workplace_id: str | None = None
    movement: AgentMovementState | None = None


@dataclass(frozen=True)
class TickAdvance:
    current_time: datetime
    tick_delta: int
    completed_movements: tuple[AgentMovementState, ...] = ()


@dataclass
class ActiveConversationState:
    id: str
    location_id: str
    participant_ids: list[str]
    active_speaker_id: str
    last_tick_no: int
    last_message_summary: str | None = None
    last_proposal: str | None = None
    open_question: str | None = None
    repeat_count: int = 0
    started_tick_no: int = 0
    turn_count: int = 0
    phase: str = "open"


@dataclass
class InteractionEdgeState:
    conversation_id: str
    source_agent_id: str
    target_agent_id: str
    last_outgoing_message: str | None = None
    last_incoming_message: str | None = None
    last_outgoing_tick_no: int | None = None
    last_incoming_tick_no: int | None = None
    last_outgoing_act: str | None = None
    last_incoming_act: str | None = None
    unresolved_item: str | None = None
    closure_state: str = "open"
    novelty_since_last_turn: bool = True
    redundancy_risk: float = 0.0


@dataclass
class RestrictionState:
    """Represents an active restriction in the world state."""

    id: str
    restriction_type: str
    scope_type: str
    scope_value: str | None
    start_tick: int
    end_tick: int | None
    reason: str | None = None


class WorldState:
    """Authoritative in-memory world state facade."""

    def __init__(
        self,
        current_time: datetime,
        current_tick: int = 0,
        tick_minutes: int = 5,
        locations: dict[str, LocationState] | None = None,
        agents: dict[str, AgentState] | None = None,
        world_effects: dict[str, Any] | None = None,
        relationship_contexts: dict[str, dict[str, dict[str, Any]]] | None = None,
        active_conversations: dict[str, ActiveConversationState] | None = None,
        interaction_edges: dict[str, InteractionEdgeState] | None = None,
        active_restrictions: dict[str, list[RestrictionState]] | None = None,
        sleep_start_hour: int = 23,
        sleep_end_hour: int = 6,
    ) -> None:
        self.current_time = current_time
        self.current_tick = current_tick
        self.tick_minutes = tick_minutes
        self.locations = locations or {}
        self.agents = agents or {}
        self.world_effects = world_effects or {}
        self.relationship_contexts = relationship_contexts or {}
        self.active_conversations = active_conversations or {}
        self.interaction_edges = interaction_edges or {}
        self.active_restrictions = active_restrictions or {}
        self.sleep_start_hour = sleep_start_hour
        self.sleep_end_hour = sleep_end_hour

    def snapshot(self) -> dict[str, Any]:
        return {
            "current_time": self.current_time.isoformat(),
            "current_tick": self.current_tick,
            "tick_minutes": self.tick_minutes,
            "clock": self.time_context(),
            "locations": {
                location_id: {
                    "name": location.name,
                    "capacity": location.capacity,
                    "occupants": sorted(location.occupants),
                    "location_type": location.location_type,
                    "x": location.x,
                    "y": location.y,
                }
                for location_id, location in self.locations.items()
            },
            "world_effects": deepcopy(self.world_effects),
            "relationship_contexts": deepcopy(self.relationship_contexts),
            "active_conversations": {
                conversation_id: {
                    "location_id": conversation.location_id,
                    "participant_ids": list(conversation.participant_ids),
                    "active_speaker_id": conversation.active_speaker_id,
                    "last_tick_no": conversation.last_tick_no,
                    "last_message_summary": conversation.last_message_summary,
                    "last_proposal": conversation.last_proposal,
                    "open_question": conversation.open_question,
                    "repeat_count": conversation.repeat_count,
                    "started_tick_no": conversation.started_tick_no,
                    "turn_count": conversation.turn_count,
                    "phase": conversation.phase,
                }
                for conversation_id, conversation in self.active_conversations.items()
            },
            "interaction_edges": {
                edge_key: {
                    "conversation_id": edge.conversation_id,
                    "source_agent_id": edge.source_agent_id,
                    "target_agent_id": edge.target_agent_id,
                    "last_outgoing_message": edge.last_outgoing_message,
                    "last_incoming_message": edge.last_incoming_message,
                    "last_outgoing_tick_no": edge.last_outgoing_tick_no,
                    "last_incoming_tick_no": edge.last_incoming_tick_no,
                    "last_outgoing_act": edge.last_outgoing_act,
                    "last_incoming_act": edge.last_incoming_act,
                    "unresolved_item": edge.unresolved_item,
                    "closure_state": edge.closure_state,
                    "novelty_since_last_turn": edge.novelty_since_last_turn,
                    "redundancy_risk": edge.redundancy_risk,
                }
                for edge_key, edge in self.interaction_edges.items()
            },
            "agents": {
                agent_id: {
                    "name": agent.name,
                    "location_id": agent.location_id,
                    "status": deepcopy(agent.status),
                    "occupation": agent.occupation,
                    "workplace_id": agent.workplace_id,
                    "movement": agent.movement.to_dict() if agent.movement else None,
                }
                for agent_id, agent in self.agents.items()
            },
        }

    def time_context(self) -> dict[str, Any]:
        weekday = self.current_time.weekday()
        minute_of_day = (self.current_time.hour * 60) + self.current_time.minute
        return {
            "current_time": self.current_time.isoformat(),
            "current_tick": self.current_tick,
            "tick_minutes": self.tick_minutes,
            "day_index": self._day_index(),
            "weekday": weekday,
            "weekday_name": self._weekday_name(weekday),
            "hour": self.current_time.hour,
            "minute": self.current_time.minute,
            "minute_of_day": minute_of_day,
            "is_weekend": weekday >= 5,
            "time_period": self._time_period(),
        }

    def advance_tick(self) -> TickAdvance:
        next_time = self.current_time + timedelta(minutes=self.tick_minutes)
        wake_time = self._resolve_sleep_jump(next_time)
        if wake_time is not None:
            advanced_minutes = int((wake_time - self.current_time).total_seconds() // 60)
            tick_delta = advanced_minutes // self.tick_minutes
            self.current_time = wake_time
        else:
            tick_delta = 1
            self.current_time = next_time

        self.current_tick += tick_delta
        completed_movements = tuple(self.complete_arrived_movements())
        return TickAdvance(
            current_time=self.current_time,
            tick_delta=tick_delta,
            completed_movements=completed_movements,
        )

    def get_agent(self, agent_id: str) -> AgentState | None:
        return self.agents.get(agent_id)

    def get_location(self, location_id: str) -> LocationState | None:
        return self.locations.get(location_id)

    def add_restriction(self, agent_id: str, restriction: RestrictionState) -> None:
        """Add an active restriction for an agent."""
        if agent_id not in self.active_restrictions:
            self.active_restrictions[agent_id] = []
        self.active_restrictions[agent_id].append(restriction)

    def has_restriction(
        self,
        agent_id: str,
        restriction_type: str,
        scope_value: str | None = None,
    ) -> bool:
        """Check if agent has an active restriction of given type."""
        if agent_id not in self.active_restrictions:
            return False
        tick = self.current_tick
        for restriction in self.active_restrictions[agent_id]:
            if restriction.restriction_type != restriction_type:
                continue
            if scope_value is not None and restriction.scope_value != scope_value:
                continue
            # Check if restriction is active at current tick
            if restriction.start_tick > tick:
                continue
            if restriction.end_tick is not None and restriction.end_tick < tick:
                continue
            return True
        return False

    def move_agent(self, agent_id: str, destination_id: str) -> None:
        agent = self.agents[agent_id]
        origin = self.locations[agent.location_id]
        destination = self.locations[destination_id]

        origin.occupants.discard(agent_id)
        destination.occupants.add(agent_id)
        agent.location_id = destination_id

    def start_agent_movement(
        self,
        agent_id: str,
        destination_id: str,
    ) -> AgentMovementState:
        agent = self.agents[agent_id]
        origin_id = agent.location_id
        topology = build_world_map(self.locations.values())
        route = (
            topology.route_between_locations(origin_id, destination_id)
            if origin_id in topology.location_entrances
            and destination_id in topology.location_entrances
            else None
        )
        movement = create_agent_movement(
            agent_id=agent_id,
            from_location_id=origin_id,
            to_location_id=destination_id,
            # Intents are committed by the tick that advance_tick() is about to publish.
            # Aligning the movement interval with that public tick keeps a fresh snapshot
            # at progress 0 instead of making the client skip the first half of the route.
            started_tick=self.current_tick + 1,
            route_node_ids=route.node_ids if route else (),
            distance=route.distance if route else 0.0,
        )
        self.locations[origin_id].occupants.discard(agent_id)
        agent.movement = movement
        return movement

    def complete_arrived_movements(self) -> list[AgentMovementState]:
        completed: list[AgentMovementState] = []
        for agent in self.agents.values():
            movement = agent.movement
            if movement is None or movement.arrival_tick > self.current_tick:
                continue
            destination = self.locations.get(movement.to_location_id)
            if destination is None:
                continue
            agent.location_id = destination.id
            agent.movement = None
            destination.occupants.add(agent.id)
            completed.append(movement)
        return completed

    def destination_occupancy(self, location_id: str) -> int:
        location = self.locations[location_id]
        reservations = sum(
            1
            for agent in self.agents.values()
            if agent.movement is not None and agent.movement.to_location_id == location_id
        )
        return len(location.occupants) + reservations

    def _day_index(self) -> int:
        return self.current_time.toordinal()

    def _weekday_name(self, weekday: int) -> str:
        names = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]
        return names[weekday]

    def _time_period(self) -> str:
        hour = self.current_time.hour
        if hour < 5:
            return "night"
        if hour < 7:
            return "dawn"
        if hour < 12:
            return "morning"
        if hour < 14:
            return "noon"
        if hour < 18:
            return "afternoon"
        if hour < 21:
            return "evening"
        return "night"

    def _resolve_sleep_jump(self, candidate_time: datetime) -> datetime | None:
        if not self._is_sleep_time(candidate_time):
            return None

        if candidate_time.hour >= self.sleep_start_hour:
            wake_date = (candidate_time + timedelta(days=1)).date()
        else:
            wake_date = candidate_time.date()

        wake_time = datetime.combine(
            wake_date,
            time(self.sleep_end_hour, 0),
            tzinfo=candidate_time.tzinfo,
        )
        return wake_time

    def _is_sleep_time(self, dt: datetime) -> bool:
        hour = dt.hour
        if self.sleep_start_hour <= self.sleep_end_hour:
            return self.sleep_start_hour <= hour < self.sleep_end_hour
        return hour >= self.sleep_start_hour or hour < self.sleep_end_hour
