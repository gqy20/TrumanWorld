from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Any
from uuid import uuid4

MOVEMENT_STATE_IN_TRANSIT = "in_transit"
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "state": self.state,
            "from_location_id": self.from_location_id,
            "to_location_id": self.to_location_id,
            "started_tick": self.started_tick,
            "arrival_tick": self.arrival_tick,
            "route_node_ids": list(self.route_node_ids),
            "distance": self.distance,
            "speed": self.speed,
        }

    def to_event_payload(self) -> dict[str, Any]:
        return {
            "movement_id": self.id,
            "state": self.state,
            "from_location_id": self.from_location_id,
            "to_location_id": self.to_location_id,
            "started_tick": self.started_tick,
            "arrival_tick": self.arrival_tick,
            "route_node_ids": list(self.route_node_ids),
            "distance": self.distance,
            "speed": self.speed,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any] | None) -> AgentMovementState | None:
        if not isinstance(value, dict) or value.get("state") != MOVEMENT_STATE_IN_TRANSIT:
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
        if arrival_tick <= started_tick:
            return None
        route_node_ids = value.get("route_node_ids", [])
        distance = value.get("distance", 0.0)
        speed = value.get("speed", DEFAULT_MOVEMENT_SPEED)
        if not isinstance(route_node_ids, list) or not all(
            isinstance(node_id, str) for node_id in route_node_ids
        ):
            route_node_ids = []
        if not isinstance(distance, int | float) or distance < 0:
            distance = 0.0
        if not isinstance(speed, int | float) or speed <= 0:
            speed = DEFAULT_MOVEMENT_SPEED
        return cls(
            id=movement_id,
            state=MOVEMENT_STATE_IN_TRANSIT,
            from_location_id=from_location_id,
            to_location_id=to_location_id,
            started_tick=started_tick,
            arrival_tick=arrival_tick,
            route_node_ids=tuple(route_node_ids),
            distance=float(distance),
            speed=float(speed),
        )


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
) -> AgentMovementState:
    safe_speed = speed if speed > 0 else DEFAULT_MOVEMENT_SPEED
    safe_duration = max(1, ceil(distance / safe_speed)) if distance > 0 else max(1, duration_ticks)
    return AgentMovementState(
        id=f"move-{agent_id}-{started_tick}-{uuid4().hex[:12]}",
        from_location_id=from_location_id,
        to_location_id=to_location_id,
        started_tick=started_tick,
        arrival_tick=started_tick + safe_duration,
        route_node_ids=route_node_ids,
        distance=distance,
        speed=safe_speed,
    )
