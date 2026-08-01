from datetime import UTC, datetime

from app.sim.world import AgentState, LocationState, WorldState
from app.sim.world_map import build_world_map


def test_world_map_builds_connected_roads_around_location_plots():
    locations = [
        LocationState(id="home", name="Home", x=0, y=0),
        LocationState(id="cafe", name="Cafe", x=2, y=1),
    ]

    topology = build_world_map(locations)
    route = topology.route_between_locations("home", "cafe")

    assert topology.location_entrances == {
        "home": "road:0:1",
        "cafe": "road:4:3",
    }
    assert route.node_ids[0] == "road:0:1"
    assert route.node_ids[-1] == "road:4:3"
    assert route.distance == 3.0
    assert all(not (node.x % 2 == 0 and node.y % 2 == 0) for node in topology.nodes.values())


def test_world_map_is_deterministic_when_locations_are_reordered():
    locations = [
        LocationState(id="home", name="Home", x=0, y=0),
        LocationState(id="cafe", name="Cafe", x=2, y=1),
        LocationState(id="park", name="Park", x=1, y=2),
    ]

    first = build_world_map(locations).to_dict()
    second = build_world_map(reversed(locations)).to_dict()

    assert first == second


def test_world_movement_duration_and_payload_follow_the_planned_route():
    world = WorldState(
        current_time=datetime(2026, 1, 1, tzinfo=UTC),
        locations={
            "home": LocationState(id="home", name="Home", x=0, y=0, occupants={"alice"}),
            "park": LocationState(id="park", name="Park", x=4, y=2),
        },
        agents={"alice": AgentState(id="alice", name="Alice", location_id="home")},
    )

    movement = world.start_agent_movement("alice", "park")

    assert movement.route_node_ids[0] == "road:0:1"
    assert movement.route_node_ids[-1] == "road:8:5"
    assert movement.distance == 6.0
    assert movement.speed == 1.5
    assert movement.arrival_tick - movement.started_tick == 4
    assert movement.to_dict()["route_node_ids"] == list(movement.route_node_ids)
