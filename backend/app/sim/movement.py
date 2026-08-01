from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

MOVEMENT_STATE_IN_TRANSIT = "in_transit"
DEFAULT_MOVEMENT_DURATION_TICKS = 2


@dataclass(slots=True)
class AgentMovementState:
    id: str
    from_location_id: str
    to_location_id: str
    started_tick: int
    arrival_tick: int
    state: str = MOVEMENT_STATE_IN_TRANSIT

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "state": self.state,
            "from_location_id": self.from_location_id,
            "to_location_id": self.to_location_id,
            "started_tick": self.started_tick,
            "arrival_tick": self.arrival_tick,
        }

    def to_event_payload(self) -> dict[str, Any]:
        return {
            "movement_id": self.id,
            "state": self.state,
            "from_location_id": self.from_location_id,
            "to_location_id": self.to_location_id,
            "started_tick": self.started_tick,
            "arrival_tick": self.arrival_tick,
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
        return cls(
            id=movement_id,
            state=MOVEMENT_STATE_IN_TRANSIT,
            from_location_id=from_location_id,
            to_location_id=to_location_id,
            started_tick=started_tick,
            arrival_tick=arrival_tick,
        )


def create_agent_movement(
    *,
    agent_id: str,
    from_location_id: str,
    to_location_id: str,
    started_tick: int,
    duration_ticks: int = DEFAULT_MOVEMENT_DURATION_TICKS,
) -> AgentMovementState:
    safe_duration = max(1, duration_ticks)
    return AgentMovementState(
        id=f"move-{agent_id}-{started_tick}-{uuid4().hex[:12]}",
        from_location_id=from_location_id,
        to_location_id=to_location_id,
        started_tick=started_tick,
        arrival_tick=started_tick + safe_duration,
    )
