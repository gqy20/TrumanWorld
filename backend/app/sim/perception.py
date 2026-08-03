from __future__ import annotations

import hashlib
from dataclasses import dataclass
from math import ceil, floor, hypot

from app.scenario.embodiment_config import SocialSpatialConfig
from app.sim.world import AgentState, WorldState
from app.sim.world_map import resolve_movement_position


@dataclass(frozen=True, slots=True)
class SpatialObservation:
    agent_id: str
    position: tuple[float, float, float]
    zone_id: str
    location_id: str | None
    state: str


@dataclass(frozen=True, slots=True)
class EncounterCandidate:
    id: str
    agent_id: str
    target_agent_id: str
    position: tuple[float, float, float]
    zone_id: str
    location_id: str | None
    distance_meters: float
    expires_at_world_time: str

    def to_event_payload(self) -> dict[str, object]:
        return {
            "encounter_id": self.id,
            "agent_id": self.agent_id,
            "target_agent_id": self.target_agent_id,
            "location_id": self.location_id,
            "zone_id": self.zone_id,
            "position_meters": list(self.position),
            "distance_meters": self.distance_meters,
            "expires_at_world_time": self.expires_at_world_time,
        }


class SpatialIndex:
    """Small deterministic grid index over authoritative agent positions."""

    def __init__(self, observations: list[SpatialObservation], *, cell_size: float) -> None:
        self._cell_size = max(cell_size, 0.1)
        self._cells: dict[tuple[str, int, int], list[SpatialObservation]] = {}
        for observation in sorted(observations, key=lambda item: item.agent_id):
            self._cells.setdefault(self._cell_key(observation), []).append(observation)

    def nearby_pairs(self) -> list[tuple[SpatialObservation, SpatialObservation]]:
        pairs: dict[tuple[str, str], tuple[SpatialObservation, SpatialObservation]] = {}
        for cell_key in sorted(self._cells):
            zone_id, cell_x, cell_z = cell_key
            left_items = self._cells[cell_key]
            candidates = [
                item
                for x_offset in (-1, 0, 1)
                for z_offset in (-1, 0, 1)
                for item in self._cells.get((zone_id, cell_x + x_offset, cell_z + z_offset), [])
            ]
            for left in left_items:
                for right in candidates:
                    if left.agent_id >= right.agent_id:
                        continue
                    pairs[(left.agent_id, right.agent_id)] = (left, right)
        return [pairs[key] for key in sorted(pairs)]

    def _cell_key(self, observation: SpatialObservation) -> tuple[str, int, int]:
        return (
            observation.zone_id,
            floor(observation.position[0] / self._cell_size),
            floor(observation.position[2] / self._cell_size),
        )


def observe_world(world: WorldState) -> list[SpatialObservation]:
    return [
        observation
        for agent in sorted(world.agents.values(), key=lambda item: item.id)
        if (observation := observe_agent(world, agent)) is not None
    ]


def observe_agent(world: WorldState, agent: AgentState) -> SpatialObservation | None:
    if agent.movement is not None and world.topology is not None:
        position = resolve_movement_position(
            agent.movement,
            world.topology,
            agent.movement.progress_at(world.current_time, world.current_tick),
        )
        if position is not None:
            return SpatialObservation(
                agent_id=agent.id,
                position=position,
                zone_id="route",
                location_id=None,
                state="paused" if agent.movement.state == "paused" else "moving",
            )

    activity = agent.activity
    if (
        activity is not None
        and activity.status == "paused"
        and activity.paused_position_meters is not None
    ):
        return SpatialObservation(
            agent_id=agent.id,
            position=activity.paused_position_meters,
            zone_id=activity.zone_id or agent.location_id,
            location_id=agent.location_id,
            state="paused",
        )
    if activity is not None and activity.is_active and world.embodiment_catalog is not None:
        resource_ids = list(activity.claimed_resource_ids)
        resource = next(
            (item for item in world.embodiment_catalog.resources if item.id in resource_ids),
            None,
        )
        if resource is not None:
            return SpatialObservation(
                agent_id=agent.id,
                position=resource.position,
                zone_id=resource.zone_id,
                location_id=agent.location_id,
                state="activity",
            )

    topology = world.topology
    entrance_id = topology.location_entrances.get(agent.location_id) if topology else None
    entrance = topology.nodes.get(entrance_id) if topology and entrance_id else None
    if entrance is not None:
        position = (entrance.x, 0.0, entrance.y)
    else:
        location = world.get_location(agent.location_id)
        if location is None or location.x is None or location.y is None:
            return None
        position = (float(location.x), 0.0, float(location.y))
    return SpatialObservation(
        agent_id=agent.id,
        position=position,
        zone_id=world.location_zone_ids.get(agent.location_id, agent.location_id),
        location_id=agent.location_id,
        state="stationary",
    )


def build_encounter_candidates(
    world: WorldState,
    config: SocialSpatialConfig,
) -> list[EncounterCandidate]:
    distance_limit = config.encounter.candidate_distance_meters
    index = SpatialIndex(observe_world(world), cell_size=distance_limit)
    cooldown_ticks = max(1, ceil(config.encounter.cooldown_minutes / max(1, world.tick_minutes)))
    candidates: list[EncounterCandidate] = []
    for left, right in index.nearby_pairs():
        distance = hypot(
            left.position[0] - right.position[0],
            left.position[2] - right.position[2],
        )
        if distance > distance_limit:
            continue
        if _has_active_conversation(world, left.agent_id, right.agent_id):
            continue
        if not _is_candidate_tick(world, left.agent_id, right.agent_id, cooldown_ticks):
            continue
        encounter_id = _encounter_id(world, left.agent_id, right.agent_id)
        midpoint = (
            round((left.position[0] + right.position[0]) / 2, 4),
            round((left.position[1] + right.position[1]) / 2, 4),
            round((left.position[2] + right.position[2]) / 2, 4),
        )
        expires_at = world.current_time.timestamp() + config.encounter.candidate_timeout_seconds
        from datetime import UTC, datetime

        candidates.append(
            EncounterCandidate(
                id=encounter_id,
                agent_id=left.agent_id,
                target_agent_id=right.agent_id,
                position=midpoint,
                zone_id=left.zone_id,
                location_id=left.location_id if left.location_id == right.location_id else None,
                distance_meters=round(distance, 3),
                expires_at_world_time=datetime.fromtimestamp(expires_at, tz=UTC).isoformat(),
            )
        )
    selected: list[EncounterCandidate] = []
    occupied_agents: set[str] = set()
    for candidate in sorted(
        candidates,
        key=lambda item: (item.distance_meters, item.agent_id, item.target_agent_id),
    ):
        if candidate.agent_id in occupied_agents or candidate.target_agent_id in occupied_agents:
            continue
        selected.append(candidate)
        occupied_agents.update((candidate.agent_id, candidate.target_agent_id))
    return sorted(selected, key=lambda item: (item.agent_id, item.target_agent_id))


def _is_candidate_tick(world: WorldState, left_id: str, right_id: str, cooldown: int) -> bool:
    material = f"{world.world_seed}:{left_id}:{right_id}".encode()
    phase = int.from_bytes(hashlib.sha256(material).digest()[:4], "big") % cooldown
    return world.current_tick % cooldown == phase


def _encounter_id(world: WorldState, left_id: str, right_id: str) -> str:
    material = f"{world.world_seed}:{world.current_tick}:{left_id}:{right_id}".encode()
    return f"encounter-{hashlib.sha256(material).hexdigest()[:16]}"


def _has_active_conversation(world: WorldState, left_id: str, right_id: str) -> bool:
    return any(
        left_id in conversation.participant_ids and right_id in conversation.participant_ids
        for conversation in world.active_conversations.values()
    )
