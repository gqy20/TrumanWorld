from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.sim.world import LocationState


def resolve_agent_location_id(
    *,
    current_location_id: str | None,
    home_location_id: str | None,
    location_states: dict[str, LocationState],
) -> str:
    location_id = current_location_id or home_location_id
    if location_id is not None:
        return location_id
    return next(iter(location_states.keys()), "unknown")
