from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Protocol

ROAD_STEP_DISTANCE = 0.5


class MappableLocation(Protocol):
    id: str
    x: int | None
    y: int | None


@dataclass(frozen=True, slots=True)
class WorldMapNode:
    id: str
    x: int
    y: int


@dataclass(frozen=True, slots=True)
class WorldMapEdge:
    from_node_id: str
    to_node_id: str
    distance: float = ROAD_STEP_DISTANCE


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

        neighbors: dict[str, list[str]] = {node_id: [] for node_id in self.nodes}
        for edge in self.edges:
            neighbors[edge.from_node_id].append(edge.to_node_id)
            neighbors[edge.to_node_id].append(edge.from_node_id)
        for node_neighbors in neighbors.values():
            node_neighbors.sort()

        queue = deque([start])
        previous: dict[str, str | None] = {start: None}
        while queue:
            current = queue.popleft()
            if current == end:
                break
            for neighbor in neighbors[current]:
                if neighbor in previous:
                    continue
                previous[neighbor] = current
                queue.append(neighbor)
        if end not in previous:
            raise ValueError(f"No navigable route from {origin_id} to {destination_id}")

        route = [end]
        while previous[route[-1]] is not None:
            route.append(previous[route[-1]])
        route.reverse()
        return WorldMapRoute(
            node_ids=tuple(route),
            distance=round((len(route) - 1) * ROAD_STEP_DISTANCE, 3),
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
            node = WorldMapNode(id=_node_id(x, y), x=x, y=y)
            nodes[node.id] = node

    edges: list[WorldMapEdge] = []
    for node in sorted(nodes.values(), key=lambda item: (item.y, item.x)):
        for dx, dy in ((1, 0), (0, 1)):
            neighbor_id = _node_id(node.x + dx, node.y + dy)
            if neighbor_id in nodes:
                edges.append(WorldMapEdge(from_node_id=node.id, to_node_id=neighbor_id))

    entrances = {
        location_id: _node_id(x * 2, y * 2 + 1) for location_id, x, y in resolved_locations
    }
    return WorldMapTopology(nodes=nodes, edges=tuple(edges), location_entrances=entrances)


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
