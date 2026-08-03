from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from math import ceil
from typing import Any
from uuid import uuid4

MOVEMENT_STATE_IN_TRANSIT = "in_transit"
MOVEMENT_STATE_PAUSED = "paused"
DEFAULT_MOVEMENT_DURATION_TICKS = 2
DEFAULT_MOVEMENT_SPEED = 1.5


@dataclass(slots=True)
class AgentMovementState:
    id: str
    from_location_id: str
    to_location_id: str
    started_tick: int
    arrival_tick: int
    state: str = MOVEMENT_STATE_IN_TRANSIT
    route_node_ids: tuple[str, ...] = ()
    distance: float = 0.0
    speed: float = DEFAULT_MOVEMENT_SPEED
    started_at_world_time: datetime | None = None
    expected_arrival_world_time: datetime | None = None
    duration_seconds: float | None = None
    activity_id: str | None = None
    paused_at_world_time: datetime | None = None
    paused_progress: float | None = None
    paused_for_encounter_id: str | None = None
    paused_for_conversation_id: str | None = None

    def to_dict(
        self, *, world_time: datetime | None = None, tick_no: int | None = None
    ) -> dict[str, Any]:
        result = {
            "id": self.id,
            "state": self.state,
            "from_location_id": self.from_location_id,
            "to_location_id": self.to_location_id,
            "started_tick": self.started_tick,
            "arrival_tick": self.arrival_tick,
            "route_node_ids": list(self.route_node_ids),
            "distance": self.distance,
            # `speed` remains during the protocol transition; its unit is now meters/second.
            "speed": self.speed,
            "speed_mps": self.speed,
            "started_at_world_time": _format_datetime(self.started_at_world_time),
            "expected_arrival_world_time": _format_datetime(self.expected_arrival_world_time),
            "duration_seconds": self.duration_seconds,
            "activity_id": self.activity_id,
            "paused_at_world_time": _format_datetime(self.paused_at_world_time),
            "paused_progress": self.paused_progress,
            "paused_for_encounter_id": self.paused_for_encounter_id,
            "paused_for_conversation_id": self.paused_for_conversation_id,
        }
        if world_time is not None and tick_no is not None:
            result["progress"] = self.progress_at(world_time, tick_no)
        return result

    def to_event_payload(self) -> dict[str, Any]:
        payload = self.to_dict()
        payload["movement_id"] = payload.pop("id")
        return payload

    @classmethod
    def from_dict(cls, value: dict[str, Any] | None) -> AgentMovementState | None:
        if not isinstance(value, dict) or value.get("state") not in {
            MOVEMENT_STATE_IN_TRANSIT,
            MOVEMENT_STATE_PAUSED,
        }:
            return None
        movement_id = value.get("id")
        from_location_id = value.get("from_location_id")
        to_location_id = value.get("to_location_id")
        started_tick = value.get("started_tick")
        arrival_tick = value.get("arrival_tick")
        if not all(
            (
                isinstance(movement_id, str),
                isinstance(from_location_id, str),
                isinstance(to_location_id, str),
                isinstance(started_tick, int),
                isinstance(arrival_tick, int),
            )
        ):
            return None
        if arrival_tick < started_tick:
            return None
        route_node_ids = value.get("route_node_ids", [])
        distance = value.get("distance", 0.0)
        speed = value.get("speed_mps", value.get("speed", DEFAULT_MOVEMENT_SPEED))
        if not isinstance(route_node_ids, list) or not all(
            isinstance(node_id, str) for node_id in route_node_ids
        ):
            route_node_ids = []
        if not isinstance(distance, int | float) or distance < 0:
            distance = 0.0
        if not isinstance(speed, int | float) or speed <= 0:
            speed = DEFAULT_MOVEMENT_SPEED
        duration_seconds = value.get("duration_seconds")
        activity_id = value.get("activity_id")
        return cls(
            id=movement_id,
            state=str(value["state"]),
            from_location_id=from_location_id,
            to_location_id=to_location_id,
            started_tick=started_tick,
            arrival_tick=arrival_tick,
            route_node_ids=tuple(route_node_ids),
            distance=float(distance),
            speed=float(speed),
            started_at_world_time=_parse_datetime(value.get("started_at_world_time")),
            expected_arrival_world_time=_parse_datetime(value.get("expected_arrival_world_time")),
            duration_seconds=(
                float(duration_seconds) if isinstance(duration_seconds, int | float) else None
            ),
            activity_id=activity_id if isinstance(activity_id, str) else None,
            paused_at_world_time=_parse_datetime(value.get("paused_at_world_time")),
            paused_progress=(
                float(value["paused_progress"])
                if isinstance(value.get("paused_progress"), int | float)
                else None
            ),
            paused_for_encounter_id=_optional_str(value.get("paused_for_encounter_id")),
            paused_for_conversation_id=_optional_str(value.get("paused_for_conversation_id")),
        )

    def arrives_by(self, world_time: datetime, tick_no: int) -> bool:
        if self.state == MOVEMENT_STATE_PAUSED:
            return False
        if self.expected_arrival_world_time is not None:
            return self.expected_arrival_world_time <= world_time
        return self.arrival_tick <= tick_no

    def progress_at(self, world_time: datetime, tick_no: int) -> float:
        if self.state == MOVEMENT_STATE_PAUSED and self.paused_progress is not None:
            return self.paused_progress
        if self.started_at_world_time is not None and self.expected_arrival_world_time is not None:
            total = max(
                0.001,
                (self.expected_arrival_world_time - self.started_at_world_time).total_seconds(),
            )
            elapsed = max(0.0, (world_time - self.started_at_world_time).total_seconds())
            return round(min(1.0, elapsed / total), 4)
        tick_duration = max(1, self.arrival_tick - self.started_tick)
        return round(min(1.0, max(0, tick_no - self.started_tick) / tick_duration), 4)

    def pause(
        self,
        world_time: datetime,
        tick_no: int,
        *,
        encounter_id: str | None,
        conversation_id: str | None,
    ) -> bool:
        if self.state == MOVEMENT_STATE_PAUSED:
            return False
        self.paused_progress = self.progress_at(world_time, tick_no)
        self.paused_at_world_time = world_time
        self.paused_for_encounter_id = encounter_id
        self.paused_for_conversation_id = conversation_id
        self.state = MOVEMENT_STATE_PAUSED
        return True

    def resume(self, world_time: datetime, tick_no: int) -> bool:
        if self.state != MOVEMENT_STATE_PAUSED:
            return False
        progress = min(1.0, max(0.0, self.paused_progress or 0.0))
        if self.duration_seconds is not None:
            elapsed_seconds = self.duration_seconds * progress
            remaining_seconds = self.duration_seconds - elapsed_seconds
            self.started_at_world_time = world_time - timedelta(seconds=elapsed_seconds)
            self.expected_arrival_world_time = world_time + timedelta(seconds=remaining_seconds)
        total_ticks = max(1, self.arrival_tick - self.started_tick)
        elapsed_ticks = min(total_ticks, int(total_ticks * progress))
        self.started_tick = tick_no - elapsed_ticks
        self.arrival_tick = self.started_tick + total_ticks
        self.state = MOVEMENT_STATE_IN_TRANSIT
        self.paused_at_world_time = None
        self.paused_progress = None
        self.paused_for_encounter_id = None
        self.paused_for_conversation_id = None
        return True


def create_agent_movement(
    *,
    agent_id: str,
    from_location_id: str,
    to_location_id: str,
    started_tick: int,
    duration_ticks: int = DEFAULT_MOVEMENT_DURATION_TICKS,
    route_node_ids: tuple[str, ...] = (),
    distance: float = 0.0,
    speed: float = DEFAULT_MOVEMENT_SPEED,
    started_at_world_time: datetime | None = None,
    tick_seconds: float = 300.0,
    activity_id: str | None = None,
) -> AgentMovementState:
    safe_speed = speed if speed > 0 else DEFAULT_MOVEMENT_SPEED
    duration_seconds = (
        max(0.001, distance / safe_speed)
        if distance > 0
        else max(1.0, duration_ticks * tick_seconds)
    )
    duration_in_ticks = max(1, ceil(duration_seconds / max(1.0, tick_seconds)))
    return AgentMovementState(
        id=f"move-{agent_id}-{started_tick}-{uuid4().hex[:12]}",
        from_location_id=from_location_id,
        to_location_id=to_location_id,
        started_tick=started_tick,
        arrival_tick=started_tick + duration_in_ticks,
        route_node_ids=route_node_ids,
        distance=distance,
        speed=safe_speed,
        started_at_world_time=started_at_world_time,
        expected_arrival_world_time=(
            started_at_world_time + timedelta(seconds=duration_seconds)
            if started_at_world_time is not None
            else None
        ),
        duration_seconds=round(duration_seconds, 4),
        activity_id=activity_id,
    )


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _format_datetime(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
