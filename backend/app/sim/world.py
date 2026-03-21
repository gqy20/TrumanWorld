from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from typing import Any


@dataclass
class LocationState:
    id: str
    name: str
    capacity: int = 10
    occupants: set[str] = field(default_factory=set)
    location_type: str | None = None


@dataclass
class AgentState:
    id: str
    name: str
    location_id: str
    status: dict[str, Any] = field(default_factory=dict)
    occupation: str | None = None
    workplace_id: str | None = None


@dataclass(frozen=True)
class TickAdvance:
    current_time: datetime
    tick_delta: int


@dataclass
class ActiveConversationState:
    id: str
    location_id: str
    participant_ids: list[str]
    active_speaker_id: str
    last_tick_no: int


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
                }
                for conversation_id, conversation in self.active_conversations.items()
            },
            "agents": {
                agent_id: {
                    "name": agent.name,
                    "location_id": agent.location_id,
                    "status": deepcopy(agent.status),
                    "occupation": agent.occupation,
                    "workplace_id": agent.workplace_id,
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
        return TickAdvance(current_time=self.current_time, tick_delta=tick_delta)

    def get_agent(self, agent_id: str) -> AgentState | None:
        return self.agents.get(agent_id)

    def get_location(self, location_id: str) -> LocationState | None:
        return self.locations.get(location_id)

    def move_agent(self, agent_id: str, destination_id: str) -> None:
        agent = self.agents[agent_id]
        origin = self.locations[agent.location_id]
        destination = self.locations[destination_id]

        origin.occupants.discard(agent_id)
        destination.occupants.add(agent_id)
        agent.location_id = destination_id

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
