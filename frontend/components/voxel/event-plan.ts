import type { SceneBubble, SceneMoveTrail } from "@/lib/world-scene-adapter";

import { snapRoadPoint } from "./road-graph";
import type { VoxelPoint, VoxelRoadTile, VoxelScenePlan, VoxelVector3 } from "./types";

export type VoxelEventBubble = SceneBubble & {
  position: VoxelVector3;
};

export type VoxelMoveTrail = SceneMoveTrail & {
  points: VoxelVector3[];
};

export type VoxelEventPlan = {
  bubbles: VoxelEventBubble[];
  moveTrails: VoxelMoveTrail[];
};

const ROAD_DIRECTIONS = [
  { dx: 0, dz: -1 },
  { dx: 1, dz: 0 },
  { dx: 0, dz: 1 },
  { dx: -1, dz: 0 },
] as const;

export function buildVoxelEventPlan(
  bubbles: SceneBubble[],
  moveTrails: SceneMoveTrail[],
  scenePlan: VoxelScenePlan,
): VoxelEventPlan {
  const plotByLocationId = new Map(
    scenePlan.plots.map((plotItem) => [plotItem.locationId, plotItem]),
  );

  return {
    bubbles: bubbles.flatMap((bubble) => {
      const agentAnchor = bubble.speakerAgentId
        ? scenePlan.agentAnchors[bubble.speakerAgentId]
        : undefined;
      if (agentAnchor) {
        return [
          {
            ...bubble,
            position: {
              x: agentAnchor.position.x,
              y: 1.18,
              z: agentAnchor.position.z,
            },
          },
        ];
      }

      const locationAnchor = scenePlan.locationAnchors[bubble.locationId];
      if (!locationAnchor) return [];
      return [
        {
          ...bubble,
          position: {
            x: locationAnchor.position.x,
            y: findLocationTop(scenePlan, bubble.locationId) + 0.34,
            z: locationAnchor.position.z,
          },
        },
      ];
    }),
    moveTrails: moveTrails.flatMap((trail) => {
      const fromPlot = plotByLocationId.get(trail.fromLocationId);
      const toPlot = plotByLocationId.get(trail.toLocationId);
      if (!fromPlot || !toPlot) return [];
      const roadPath = findRoadPath(
        scenePlan.roads,
        snapRoadPoint(fromPlot.entrance),
        snapRoadPoint(toPlot.entrance),
      );
      if (roadPath.length < 2) return [];
      return [
        {
          ...trail,
          points: roadPath.map((point) => ({ ...point, y: 0.19 })),
        },
      ];
    }),
  };
}

export function findRoadPath(
  roads: VoxelRoadTile[],
  start: VoxelPoint,
  end: VoxelPoint,
): VoxelPoint[] {
  const roadByKey = new Map(roads.map((road) => [pointKey(road), road]));
  const startKey = pointKey(start);
  const endKey = pointKey(end);
  if (!roadByKey.has(startKey) || !roadByKey.has(endKey)) return [];
  if (startKey === endKey) return [start];

  const queue = [startKey];
  const visited = new Set([startKey]);
  const cameFrom = new Map<string, string>();

  while (queue.length > 0) {
    const currentKey = queue.shift() as string;
    const current = roadByKey.get(currentKey) as VoxelRoadTile;
    for (const direction of ROAD_DIRECTIONS) {
      const neighbor = { x: current.x + direction.dx, z: current.z + direction.dz };
      const neighborKey = pointKey(neighbor);
      if (!roadByKey.has(neighborKey) || visited.has(neighborKey)) continue;
      visited.add(neighborKey);
      cameFrom.set(neighborKey, currentKey);
      if (neighborKey === endKey) return reconstructPath(cameFrom, startKey, endKey);
      queue.push(neighborKey);
    }
  }

  return [];
}

function reconstructPath(
  cameFrom: Map<string, string>,
  startKey: string,
  endKey: string,
): VoxelPoint[] {
  const path = [keyToPoint(endKey)];
  let currentKey = endKey;
  while (currentKey !== startKey) {
    const previousKey = cameFrom.get(currentKey);
    if (!previousKey) return [];
    currentKey = previousKey;
    path.push(keyToPoint(currentKey));
  }
  return path.reverse();
}

function findLocationTop(scenePlan: VoxelScenePlan, locationId: string): number {
  return scenePlan.blocks.reduce((top, block) => {
    if (block.hitTarget?.kind !== "location" || block.hitTarget.id !== locationId) return top;
    return Math.max(top, block.position.y + block.size.y / 2);
  }, 0.8);
}

function pointKey(point: VoxelPoint): string {
  return `${point.x}:${point.z}`;
}

function keyToPoint(key: string): VoxelPoint {
  const [x, z] = key.split(":").map(Number);
  return { x, z };
}
