from datetime import UTC, datetime
from itertools import pairwise

from app.scenario.embodiment_config import (
    EncounterDefinition,
    PerceptionDefinition,
    SocialSpatialConfig,
)
from app.sim.movement import AgentMovementState
from app.sim.perception import build_encounter_candidates, observe_world
from app.sim.runner import SimulationRunner
from app.sim.world import AgentState, LocationState, WorldState
from app.sim.world_map import WorldMapNode, WorldMapTopology


def _config(*, cooldown_minutes: int = 5) -> SocialSpatialConfig:
    return SocialSpatialConfig(
        perception=PerceptionDefinition(
            vision_range_meters=8,
            conversation_range_meters=1.8,
            hearing_range_meters=5,
        ),
        encounter=EncounterDefinition(
            candidate_distance_meters=2.5,
            candidate_timeout_seconds=15,
            cooldown_minutes=cooldown_minutes,
        ),
    )


def _world(*, tick: int = 0, second_zone: str = "zone-quad") -> WorldState:
    location_a = LocationState(id="run-quad", name="Quad", x=0, y=0)
    location_b = LocationState(id="run-quad-side", name="Quad Side", x=1, y=0)
    return WorldState(
        current_time=datetime(2026, 3, 2, 8, 0, tzinfo=UTC),
        current_tick=tick,
        tick_minutes=5,
        locations={location_a.id: location_a, location_b.id: location_b},
        agents={
            "alice": AgentState(id="alice", name="Alice", location_id=location_a.id),
            "bob": AgentState(id="bob", name="Bob", location_id=location_b.id),
        },
        topology=WorldMapTopology(
            nodes={
                "a": WorldMapNode(id="a", x=0, y=0),
                "b": WorldMapNode(id="b", x=1, y=0),
            },
            edges=(),
            location_entrances={location_a.id: "a", location_b.id: "b"},
        ),
        location_zone_ids={location_a.id: "zone-quad", location_b.id: second_zone},
        world_seed=7,
    )


def test_spatial_observations_use_authoritative_positions_and_zones() -> None:
    observations = observe_world(_world())

    assert [(item.agent_id, item.position, item.zone_id) for item in observations] == [
        ("alice", (0, 0.0, 0), "zone-quad"),
        ("bob", (1, 0.0, 0), "zone-quad"),
    ]


def test_spatial_observation_exposes_paused_route_state() -> None:
    world = _world()
    world.agents["alice"].movement = AgentMovementState(
        id="move-alice",
        from_location_id="run-quad",
        to_location_id="run-quad-side",
        started_tick=0,
        arrival_tick=2,
        state="paused",
        route_node_ids=("a", "b"),
        paused_progress=0.5,
    )

    observation = next(item for item in observe_world(world) if item.agent_id == "alice")

    assert observation.position == (0.5, 0.0, 0.0)
    assert observation.zone_id == "route"
    assert observation.state == "paused"


def test_encounter_candidates_are_deterministic_for_same_seed_and_tick() -> None:
    first = build_encounter_candidates(_world(), _config())
    second = build_encounter_candidates(_world(), _config())

    assert len(first) == 1
    assert first == second
    assert first[0].distance_meters == 1
    assert first[0].agent_id == "alice"
    assert first[0].target_agent_id == "bob"


def test_encounter_candidates_respect_zone_visibility() -> None:
    candidates = build_encounter_candidates(_world(second_zone="zone-library"), _config())

    assert candidates == []


def test_encounter_candidates_use_a_seeded_cooldown_phase() -> None:
    generated_ticks = [
        tick
        for tick in range(12)
        if build_encounter_candidates(_world(tick=tick), _config(cooldown_minutes=15))
    ]

    assert len(generated_ticks) == 4
    assert all(right - left == 3 for left, right in pairwise(generated_ticks))


def test_runner_emits_authoritative_encounter_candidate_after_spatial_advance() -> None:
    world = _world()
    world.social_spatial_config = _config()

    result = SimulationRunner(world).tick([])

    candidate = next(
        item for item in result.accepted if item.action_type == "encounter_candidate_created"
    )
    assert candidate.event_payload["agent_id"] == "alice"
    assert candidate.event_payload["target_agent_id"] == "bob"
    assert candidate.event_payload["position_meters"] == [0.5, 0.0, 0.0]
