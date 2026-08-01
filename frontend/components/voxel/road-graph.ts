import type { SceneNavigation } from "@/lib/world-scene-adapter";

import type { VoxelPlot, VoxelPoint, VoxelRoadConnections, VoxelRoadTile } from "./types";

type GridBounds = {
  minX: number;
  maxX: number;
  minZ: number;
  maxZ: number;
};

type SearchNode = VoxelPoint & {
  fScore: number;
  gScore: number;
};

const DIRECTIONS = [
  { name: "north", dx: 0, dz: -1, opposite: "south" },
  { name: "east", dx: 1, dz: 0, opposite: "west" },
  { name: "south", dx: 0, dz: 1, opposite: "north" },
  { name: "west", dx: -1, dz: 0, opposite: "east" },
] as const;

export function buildRoadGraph(
  plots: VoxelPlot[],
  navigation?: SceneNavigation,
): VoxelRoadTile[] {
  if (navigation?.nodes.length) return buildAuthoritativeRoadGraph(plots, navigation);
  if (plots.length === 0) return [];

  const sortedPlots = plots.slice().sort((left, right) => left.locationId.localeCompare(right.locationId));
  const bounds = calculateSearchBounds(sortedPlots);
  const blocked = buildBlockedTileSet(sortedPlots, bounds);
  const starts = sortedPlots.map((plotItem) => snapPoint(plotItem.entrance));
  const preferredHub = resolvePreferredHub(sortedPlots, starts);
  const hub = findOpenHub(preferredHub, blocked, bounds);
  const network = new Set<string>([pointKey(hub)]);
  const usage = new Map<string, number>([[pointKey(hub), 0]]);

  starts.forEach((start) => {
    const path = findPath(start, hub, blocked, network, bounds);
    for (const point of path) {
      const key = pointKey(point);
      network.add(key);
      usage.set(key, (usage.get(key) ?? 0) + 1);
    }
  });

  return Array.from(network, keyToPoint)
    .sort(comparePoints)
    .map((point) => {
      const key = pointKey(point);
      return {
        ...point,
        role: key === pointKey(hub) ? "plaza" : (usage.get(key) ?? 0) > 1 ? "main" : "connector",
        connections: buildConnections(point, network),
      };
    });
}

function buildAuthoritativeRoadGraph(
  plots: VoxelPlot[],
  navigation: SceneNavigation,
): VoxelRoadTile[] {
  const neighbors = new Map(navigation.nodes.map((node) => [node.id, new Set<string>()]));
  for (const edge of navigation.edges) {
    neighbors.get(edge.fromNodeId)?.add(edge.toNodeId);
    neighbors.get(edge.toNodeId)?.add(edge.fromNodeId);
  }
  const centerLocation = plots.find((plotItem) => plotItem.district === "center")?.locationId;
  const plazaNodeId = centerLocation
    ? navigation.locationEntrances[centerLocation]
    : undefined;
  return navigation.nodes
    .slice()
    .sort((left, right) => left.z - right.z || left.x - right.x || left.id.localeCompare(right.id))
    .map((node) => {
      const adjacent = neighbors.get(node.id) ?? new Set<string>();
      const adjacentPoints = Array.from(adjacent)
        .map((nodeId) => navigation.nodes.find((candidate) => candidate.id === nodeId))
        .filter((candidate): candidate is SceneNavigation["nodes"][number] => Boolean(candidate));
      return {
        nodeId: node.id,
        x: node.x,
        z: node.z,
        role: node.id === plazaNodeId ? "plaza" : adjacent.size > 2 ? "main" : "connector",
        connections: {
          north: adjacentPoints.some((point) => point.x === node.x && point.z === node.z - 1),
          east: adjacentPoints.some((point) => point.x === node.x + 1 && point.z === node.z),
          south: adjacentPoints.some((point) => point.x === node.x && point.z === node.z + 1),
          west: adjacentPoints.some((point) => point.x === node.x - 1 && point.z === node.z),
        },
      } satisfies VoxelRoadTile;
    });
}

export function snapRoadPoint(point: VoxelPoint): VoxelPoint {
  return snapPoint(point);
}

function findPath(
  start: VoxelPoint,
  goal: VoxelPoint,
  blocked: Set<string>,
  network: Set<string>,
  bounds: GridBounds,
): VoxelPoint[] {
  const startKey = pointKey(start);
  const goalKey = pointKey(goal);
  const open = new Map<string, SearchNode>([
    [startKey, { ...start, gScore: 0, fScore: manhattanDistance(start, goal) }],
  ]);
  const cameFrom = new Map<string, string>();
  const gScores = new Map<string, number>([[startKey, 0]]);
  const closed = new Set<string>();

  while (open.size > 0) {
    const current = Array.from(open.values()).sort(compareSearchNodes)[0];
    const currentKey = pointKey(current);
    open.delete(currentKey);
    if (currentKey === goalKey) return reconstructPath(cameFrom, currentKey);
    closed.add(currentKey);

    for (const neighbor of getNeighbors(current, bounds)) {
      const neighborKey = pointKey(neighbor);
      if (closed.has(neighborKey)) continue;
      if (blocked.has(neighborKey) && neighborKey !== startKey && neighborKey !== goalKey) continue;

      const stepCost = network.has(neighborKey) ? 0.45 : 1;
      const tentativeScore = current.gScore + stepCost;
      if (tentativeScore >= (gScores.get(neighborKey) ?? Number.POSITIVE_INFINITY)) continue;

      cameFrom.set(neighborKey, currentKey);
      gScores.set(neighborKey, tentativeScore);
      open.set(neighborKey, {
        ...neighbor,
        gScore: tentativeScore,
        fScore: tentativeScore + manhattanDistance(neighbor, goal),
      });
    }
  }

  throw new Error(`Unable to connect road entrance ${startKey} to hub ${goalKey}`);
}

function reconstructPath(cameFrom: Map<string, string>, goalKey: string): VoxelPoint[] {
  const path = [keyToPoint(goalKey)];
  let currentKey = goalKey;
  while (cameFrom.has(currentKey)) {
    currentKey = cameFrom.get(currentKey) as string;
    path.push(keyToPoint(currentKey));
  }
  return path.reverse();
}

function findOpenHub(
  preferred: VoxelPoint,
  blocked: Set<string>,
  bounds: GridBounds,
): VoxelPoint {
  const candidates: VoxelPoint[] = [];
  const maxRadius = Math.max(bounds.maxX - bounds.minX, bounds.maxZ - bounds.minZ);
  for (let radius = 0; radius <= maxRadius; radius += 1) {
    for (let x = preferred.x - radius; x <= preferred.x + radius; x += 1) {
      for (let z = preferred.z - radius; z <= preferred.z + radius; z += 1) {
        if (Math.abs(x - preferred.x) + Math.abs(z - preferred.z) !== radius) continue;
        if (!isWithinBounds({ x, z }, bounds)) continue;
        candidates.push({ x, z });
      }
    }
    const openCandidate = candidates.sort(comparePoints).find((point) => !blocked.has(pointKey(point)));
    if (openCandidate) return openCandidate;
  }
  throw new Error("Unable to find an open road hub");
}

function resolvePreferredHub(plots: VoxelPlot[], starts: VoxelPoint[]): VoxelPoint {
  const centerPlot = plots.find((plotItem) => plotItem.district === "center");
  if (centerPlot) return snapPoint(centerPlot.entrance);
  return snapPoint({
    x: starts.reduce((total, point) => total + point.x, 0) / starts.length,
    z: starts.reduce((total, point) => total + point.z, 0) / starts.length,
  });
}

function buildBlockedTileSet(plots: VoxelPlot[], bounds: GridBounds): Set<string> {
  const blocked = new Set<string>();
  for (let x = bounds.minX; x <= bounds.maxX; x += 1) {
    for (let z = bounds.minZ; z <= bounds.maxZ; z += 1) {
      if (plots.some((plotItem) => isInsideFootprint({ x, z }, plotItem))) {
        blocked.add(pointKey({ x, z }));
      }
    }
  }
  return blocked;
}

function isInsideFootprint(point: VoxelPoint, plotItem: VoxelPlot): boolean {
  const halfWidth = plotItem.footprint.width / 2 + 0.05;
  const halfDepth = plotItem.footprint.depth / 2 + 0.05;
  return (
    Math.abs(point.x - plotItem.center.x) < halfWidth &&
    Math.abs(point.z - plotItem.center.z) < halfDepth
  );
}

function calculateSearchBounds(plots: VoxelPlot[]): GridBounds {
  const xs = plots.flatMap((plotItem) => [
    plotItem.center.x - plotItem.size.width / 2,
    plotItem.center.x + plotItem.size.width / 2,
    plotItem.entrance.x,
  ]);
  const zs = plots.flatMap((plotItem) => [
    plotItem.center.z - plotItem.size.depth / 2,
    plotItem.center.z + plotItem.size.depth / 2,
    plotItem.entrance.z,
  ]);
  return {
    minX: Math.floor(Math.min(...xs, 0)) - 2,
    maxX: Math.ceil(Math.max(...xs, 0)) + 2,
    minZ: Math.floor(Math.min(...zs, 0)) - 2,
    maxZ: Math.ceil(Math.max(...zs, 0)) + 2,
  };
}

function buildConnections(point: VoxelPoint, network: Set<string>): VoxelRoadConnections {
  return {
    north: network.has(pointKey({ x: point.x, z: point.z - 1 })),
    east: network.has(pointKey({ x: point.x + 1, z: point.z })),
    south: network.has(pointKey({ x: point.x, z: point.z + 1 })),
    west: network.has(pointKey({ x: point.x - 1, z: point.z })),
  };
}

function getNeighbors(point: VoxelPoint, bounds: GridBounds): VoxelPoint[] {
  return DIRECTIONS.map((direction) => ({
    x: point.x + direction.dx,
    z: point.z + direction.dz,
  })).filter((candidate) => isWithinBounds(candidate, bounds));
}

function isWithinBounds(point: VoxelPoint, bounds: GridBounds): boolean {
  return (
    point.x >= bounds.minX &&
    point.x <= bounds.maxX &&
    point.z >= bounds.minZ &&
    point.z <= bounds.maxZ
  );
}

function compareSearchNodes(left: SearchNode, right: SearchNode): number {
  return (
    left.fScore - right.fScore ||
    left.gScore - right.gScore ||
    comparePoints(left, right)
  );
}

function comparePoints(left: VoxelPoint, right: VoxelPoint): number {
  return left.z - right.z || left.x - right.x;
}

function manhattanDistance(left: VoxelPoint, right: VoxelPoint): number {
  return Math.abs(left.x - right.x) + Math.abs(left.z - right.z);
}

function snapPoint(point: VoxelPoint): VoxelPoint {
  return { x: Math.round(point.x), z: Math.round(point.z) };
}

function pointKey(point: VoxelPoint): string {
  return `${point.x}:${point.z}`;
}

function keyToPoint(key: string): VoxelPoint {
  const [x, z] = key.split(":").map(Number);
  return { x, z };
}
