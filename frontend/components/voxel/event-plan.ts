import type { SceneBubble, SceneMoveTrail } from "@/lib/world-scene-adapter";

import { snapRoadPoint } from "./road-graph";
import type { VoxelPoint, VoxelRoadTile, VoxelScenePlan, VoxelVector3 } from "./types";

export type VoxelEventBubble = SceneBubble & {
  position: VoxelVector3;
};

export type VoxelMoveTrail = SceneMoveTrail & {
  formation: VoxelMovementFormation;
  junctions: VoxelMovementJunction[];
  points: VoxelVector3[];
};

export type VoxelMovementJunction = {
  id: string;
  position: VoxelVector3;
};

export type VoxelMovementFormation = {
  id: string;
  laneOffset: number;
  longitudinalOffset: number;
  memberIndex: number;
  size: number;
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
  const formationByTrailId = buildVoxelMovementFormations(moveTrails);

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
      const authoritativePath = trail.routeNodeIds
        ?.map((nodeId) => scenePlan.roads.find((road) => road.nodeId === nodeId))
        .filter((road): road is VoxelRoadTile => Boolean(road))
        .map(({ x, z }) => ({ x, z }));
      const roadPath = authoritativePath?.length
        ? authoritativePath
        : findRoadPath(
            scenePlan.roads,
            snapRoadPoint(fromPlot.entrance),
            snapRoadPoint(toPlot.entrance),
          );
      if (roadPath.length === 0) return [];
      const fromAnchor = resolveAgentPathAnchor(
        scenePlan,
        trail.actorId,
        trail.fromLocationId,
        fromPlot.agentAnchors,
      );
      const toAnchor = resolveAgentPathAnchor(
        scenePlan,
        trail.actorId,
        trail.toLocationId,
        toPlot.agentAnchors,
      );
      const points = [
        { ...fromAnchor, y: 0 },
        { ...fromPlot.entrance, y: 0 },
        ...roadPath.map((point) => ({ ...point, y: 0 })),
        { ...toPlot.entrance, y: 0 },
        { ...toAnchor, y: 0 },
      ].filter((point, index, allPoints) => {
        const previous = allPoints[index - 1];
        return !previous || previous.x !== point.x || previous.z !== point.z;
      });
      const roadByKey = new Map(scenePlan.roads.map((road) => [pointKey(road), road]));
      const junctions = roadPath.flatMap((point) => {
        const road = roadByKey.get(pointKey(point));
        if (!road || countRoadConnections(road) < 3) return [];
        return [{ id: `junction:${pointKey(point)}`, position: { ...point, y: 0 } }];
      });
      return [
        {
          ...trail,
          formation: formationByTrailId.get(trail.id) ?? createSoloFormation(trail),
          junctions,
          points,
        },
      ];
    }),
  };
}

function countRoadConnections(road: VoxelRoadTile): number {
  return Object.values(road.connections).filter(Boolean).length;
}

export function buildVoxelMovementFormations(
  moveTrails: SceneMoveTrail[],
): Map<string, VoxelMovementFormation> {
  const groups = new Map<string, SceneMoveTrail[]>();
  for (const trail of moveTrails) {
    const routeKey = trail.routeNodeIds?.join(",") ?? "fallback";
    const key = `${trail.fromLocationId}>${trail.toLocationId}:${routeKey}`;
    const group = groups.get(key) ?? [];
    group.push(trail);
    groups.set(key, group);
  }

  const formations = new Map<string, VoxelMovementFormation>();
  for (const [key, trails] of groups) {
    const members = trails.slice().sort((left, right) =>
      (left.actorId ?? left.actorName).localeCompare(right.actorId ?? right.actorName)
      || left.id.localeCompare(right.id),
    );
    members.forEach((trail, memberIndex) => {
      const rowIndex = Math.floor(memberIndex / 2);
      const isUnpairedLastMember = memberIndex === members.length - 1 && members.length % 2 === 1;
      formations.set(trail.id, {
        id: `formation:${key}`,
        laneOffset: members.length === 1 || isUnpairedLastMember
          ? 0.09
          : memberIndex % 2 === 0 ? 0 : 0.18,
        longitudinalOffset: rowIndex * 0.42,
        memberIndex,
        size: members.length,
      });
    });
  }
  return formations;
}

function createSoloFormation(trail: SceneMoveTrail): VoxelMovementFormation {
  return {
    id: `formation:${trail.fromLocationId}>${trail.toLocationId}`,
    laneOffset: 0.09,
    longitudinalOffset: 0,
    memberIndex: 0,
    size: 1,
  };
}

function resolveAgentPathAnchor(
  scenePlan: VoxelScenePlan,
  agentId: string | undefined,
  locationId: string,
  fallbackAnchors: VoxelPoint[],
): VoxelPoint {
  if (agentId) {
    const currentAgent = scenePlan.agents.find((agent) => agent.id === agentId);
    if (currentAgent?.source.locationId === locationId) {
      return {
        x: currentAgent.anchor.position.x,
        z: currentAgent.anchor.position.z,
      };
    }

    const expectedOccupants = scenePlan.agents
      .filter((agent) => agent.source.locationId === locationId && agent.id !== agentId)
      .map((agent) => agent.id)
      .concat(agentId)
      .sort((left, right) => left.localeCompare(right));
    const slotIndex = expectedOccupants.indexOf(agentId);
    const expectedAnchor = fallbackAnchors[slotIndex % fallbackAnchors.length];
    if (expectedAnchor) return expectedAnchor;
  }
  return fallbackAnchors[0];
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
