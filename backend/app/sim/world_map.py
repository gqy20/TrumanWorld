from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from heapq import heappop, heappush
from itertools import pairwise
from typing import Any, Protocol

from app.sim.movement import AgentMovementState

ROAD_STEP_DISTANCE = 0.5


class MappableLocation(Protocol):
    id: str
    x: int | None
    y: int | None


@dataclass(frozen=True, slots=True)
class WorldMapNode:
    id: str
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class WorldMapEdge:
    from_node_id: str
    to_node_id: str
    distance: float = ROAD_STEP_DISTANCE
    bidirectional: bool = True


@dataclass(frozen=True, slots=True)
class WorldMapRoute:
    node_ids: tuple[str, ...]
    distance: float


@dataclass(slots=True)
class WorldMapTopology:
    nodes: dict[str, WorldMapNode]
    edges: tuple[WorldMapEdge, ...]
    location_entrances: dict[str, str]

    def route_between_locations(self, origin_id: str, destination_id: str) -> WorldMapRoute:
        start = self.location_entrances[origin_id]
        end = self.location_entrances[destination_id]
        if start == end:
            return WorldMapRoute(node_ids=(start,), distance=0.0)

        neighbors: dict[str, list[tuple[str, float]]] = {node_id: [] for node_id in self.nodes}
        for edge in self.edges:
            neighbors[edge.from_node_id].append((edge.to_node_id, edge.distance))
            if edge.bidirectional:
                neighbors[edge.to_node_id].append((edge.from_node_id, edge.distance))
        for node_neighbors in neighbors.values():
            node_neighbors.sort(key=lambda item: item[0])

        queue: list[tuple[float, str]] = [(0.0, start)]
        distances = {start: 0.0}
        previous: dict[str, str | None] = {start: None}
        while queue:
            current_distance, current = heappop(queue)
            if current_distance > distances[current]:
                continue
            if current == end:
                break
            for neighbor, edge_distance in neighbors[current]:
                candidate = current_distance + edge_distance
                if candidate >= distances.get(neighbor, float("inf")):
                    continue
                distances[neighbor] = candidate
                previous[neighbor] = current
                heappush(queue, (candidate, neighbor))
        if end not in previous:
            raise ValueError(f"No navigable route from {origin_id} to {destination_id}")

        route = [end]
        while previous[route[-1]] is not None:
            route.append(previous[route[-1]])
        route.reverse()
        return WorldMapRoute(
            node_ids=tuple(route),
            distance=round(distances[end], 3),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "nodes": [
                {"id": node.id, "x": node.x, "y": node.y}
                for node in sorted(self.nodes.values(), key=lambda item: item.id)
            ],
            "edges": [
                {
                    "from_node_id": edge.from_node_id,
                    "to_node_id": edge.to_node_id,
                    "distance": edge.distance,
                    "bidirectional": edge.bidirectional,
                }
                for edge in self.edges
            ],
            "location_entrances": dict(sorted(self.location_entrances.items())),
        }


def build_world_map(locations: Iterable[MappableLocation]) -> WorldMapTopology:
    positioned = sorted(
        (location for location in locations if location.x is not None and location.y is not None),
        key=lambda location: location.id,
    )
    if not positioned:
        return WorldMapTopology(nodes={}, edges=(), location_entrances={})

    occupied_coordinates: set[tuple[int, int]] = set()
    resolved_locations: list[tuple[str, int, int]] = []
    for location in positioned:
        coordinate = (int(location.x), int(location.y))
        if coordinate in occupied_coordinates:
            coordinate = _find_open_coordinate(coordinate, occupied_coordinates)
        occupied_coordinates.add(coordinate)
        resolved_locations.append((location.id, coordinate[0], coordinate[1]))

    min_x = min(x * 2 for _, x, _ in resolved_locations) - 1
    max_x = max(x * 2 for _, x, _ in resolved_locations) + 1
    min_y = min(y * 2 for _, _, y in resolved_locations) - 1
    max_y = max(y * 2 for _, _, y in resolved_locations) + 1

    nodes: dict[str, WorldMapNode] = {}
    for y in range(min_y, max_y + 1):
        for x in range(min_x, max_x + 1):
            if x % 2 == 0 and y % 2 == 0:
                continue
            node = WorldMapNode(
                id=_node_id(x, y),
                x=x * ROAD_STEP_DISTANCE,
                y=y * ROAD_STEP_DISTANCE,
            )
            nodes[node.id] = node

    edges: list[WorldMapEdge] = []
    for y in range(min_y, max_y + 1):
        for x in range(min_x, max_x + 1):
            node_id = _node_id(x, y)
            if node_id not in nodes:
                continue
            for dx, dy in ((1, 0), (0, 1)):
                neighbor_id = _node_id(x + dx, y + dy)
                if neighbor_id in nodes:
                    edges.append(WorldMapEdge(from_node_id=node_id, to_node_id=neighbor_id))

    entrances = {
        location_id: _node_id(x * 2, y * 2 + 1) for location_id, x, y in resolved_locations
    }
    return WorldMapTopology(nodes=nodes, edges=tuple(edges), location_entrances=entrances)


def build_authoritative_world_map(
    locations: Iterable[MappableLocation],
    *,
    scenario_id: str | None,
    run_id: str,
) -> WorldMapTopology:
    location_list = list(locations)
    from app.scenario.spatial_manifest import load_world_map_manifest_for_scenario

    manifest = load_world_map_manifest_for_scenario(scenario_id)
    if manifest is None:
        return build_world_map(location_list)
    manifest_locations = {location.id: location for location in manifest.locations}
    entrances: dict[str, str] = {}
    for location in location_list:
        canonical_id = (
            location.id[len(run_id) + 1 :] if location.id.startswith(f"{run_id}-") else location.id
        )
        manifest_location = manifest_locations.get(canonical_id)
        if manifest_location is None:
            return build_world_map(location_list)
        entrances[location.id] = manifest_location.entrance_node_id
    return WorldMapTopology(
        nodes={
            node.id: WorldMapNode(id=node.id, x=node.position[0], y=node.position[2])
            for node in manifest.route_nodes
        },
        edges=tuple(
            WorldMapEdge(
                from_node_id=edge.from_node_id,
                to_node_id=edge.to_node_id,
                distance=edge.distance_meters,
                bidirectional=edge.bidirectional,
            )
            for edge in manifest.route_edges
        ),
        location_entrances=entrances,
    )


def resolve_movement_position(
    movement: AgentMovementState,
    topology: WorldMapTopology,
    progress: float,
) -> tuple[float, float, float] | None:
    nodes = [topology.nodes.get(node_id) for node_id in movement.route_node_ids]
    if not nodes or any(node is None for node in nodes):
        return None
    points = [(node.x, node.y) for node in nodes if node]
    if len(points) == 1:
        return (points[0][0], 0.0, points[0][1])
    segment_lengths = [
        ((right[0] - left[0]) ** 2 + (right[1] - left[1]) ** 2) ** 0.5
        for left, right in pairwise(points)
    ]
    total = sum(segment_lengths)
    remaining = min(1.0, max(0.0, progress)) * total
    for index, segment_length in enumerate(segment_lengths):
        if remaining <= segment_length or index == len(segment_lengths) - 1:
            ratio = remaining / max(segment_length, 0.001)
            left, right = points[index], points[index + 1]
            return (
                round(left[0] + ((right[0] - left[0]) * ratio), 4),
                0.0,
                round(left[1] + ((right[1] - left[1]) * ratio), 4),
            )
        remaining -= segment_length
    return None


def _node_id(x: int, y: int) -> str:
    return f"road:{x}:{y}"


def _find_open_coordinate(
    origin: tuple[int, int],
    occupied: set[tuple[int, int]],
) -> tuple[int, int]:
    for radius in range(1, len(occupied) + 2):
        candidates = [
            (origin[0] + dx, origin[1] + dy)
            for dy in range(-radius, radius + 1)
            for dx in range(-radius, radius + 1)
            if abs(dx) + abs(dy) == radius
        ]
        available = next(
            (
                point
                for point in sorted(candidates, key=lambda p: (p[1], p[0]))
                if point not in occupied
            ),
            None,
        )
        if available is not None:
            return available
    raise ValueError("Unable to place location on world map")
