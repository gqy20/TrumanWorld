import type { SceneLocation, SceneNavigation } from "@/lib/world-scene-adapter";

import type { VoxelPlot, VoxelPoint, VoxelSize } from "./types";
import {
  VOXEL_AGENT_FORMATION_OFFSETS,
  VOXEL_CONVERSATION_OFFSETS,
  VOXEL_REST_OFFSETS,
  VOXEL_WORK_OFFSETS,
} from "./scene-scale";
import { resolveVoxelLocationSpec } from "./voxel-kit";

export function buildVoxelPlots(
  locations: SceneLocation[],
  navigation?: SceneNavigation,
): VoxelPlot[] {
  const nodes = new Map(navigation?.nodes.map((node) => [node.id, node]) ?? []);
  const occupied = new Set<string>();
  return locations
    .slice()
    .sort((left, right) => left.id.localeCompare(right.id))
    .map((location) => {
      const entranceNode = nodes.get(navigation?.locationEntrances[location.id] ?? "");
      const fallback = resolveFallbackCenter(location, occupied);
      const center = entranceNode
        ? { x: entranceNode.x, z: entranceNode.z - 1 }
        : fallback;
      occupied.add(pointKey(center));
      const entrance = entranceNode
        ? { x: entranceNode.x, z: entranceNode.z }
        : { x: center.x, z: center.z + 1 };
      const spec = resolveVoxelLocationSpec(
        location.locationType,
        location.visual.visualPreset,
      );
      return {
        id: `plot-${location.id}`,
        locationId: location.id,
        locationType: location.locationType,
        district: spec.district,
        center,
        size: spec.size,
        footprint: spec.footprint,
        entrance,
        agentAnchors: buildAgentAnchors(center, entrance, VOXEL_AGENT_FORMATION_OFFSETS),
        activityAnchors: {
          talking: buildAgentAnchors(center, entrance, VOXEL_CONVERSATION_OFFSETS),
          working: buildAgentAnchors(center, entrance, VOXEL_WORK_OFFSETS),
          resting: buildAgentAnchors(center, entrance, VOXEL_REST_OFFSETS),
        },
        decorationAnchors: buildDecorationAnchors(center, spec.size),
        source: location,
      };
    });
}

export function findPlotForLocation(plots: VoxelPlot[], locationId: string): VoxelPlot | undefined {
  return plots.find((plotItem) => plotItem.locationId === locationId);
}

function resolveFallbackCenter(location: SceneLocation, occupied: Set<string>): VoxelPoint {
  const origin = { x: location.x * 2, z: location.y * 2 };
  if (!occupied.has(pointKey(origin))) return origin;
  for (let radius = 1; radius <= occupied.size + 1; radius += 1) {
    for (let z = origin.z - radius * 2; z <= origin.z + radius * 2; z += 2) {
      for (let x = origin.x - radius * 2; x <= origin.x + radius * 2; x += 2) {
        const candidate = { x, z };
        if (!occupied.has(pointKey(candidate))) return candidate;
      }
    }
  }
  return origin;
}

function buildAgentAnchors(
  center: VoxelPoint,
  entrance: VoxelPoint,
  offsets: ReadonlyArray<VoxelPoint>,
): VoxelPoint[] {
  const deltaX = entrance.x - center.x;
  const deltaZ = entrance.z - center.z;
  const distance = Math.hypot(deltaX, deltaZ) || 1;
  const forward = { x: deltaX / distance, z: deltaZ / distance };
  const right = { x: forward.z, z: -forward.x };
  return offsets.map((offset) => ({
    x: entrance.x + right.x * offset.x + forward.x * offset.z,
    z: entrance.z + right.z * offset.x + forward.z * offset.z,
  }));
}

function buildDecorationAnchors(center: VoxelPoint, size: VoxelSize): VoxelPlot["decorationAnchors"] {
  return [
    { kind: "tree", x: center.x - size.width / 2 + 0.28, z: center.z - size.depth / 2 + 0.28 },
    { kind: "lamp", x: center.x + size.width / 2 - 0.24, z: center.z + size.depth / 2 - 0.3 },
    { kind: "flowers", x: center.x - size.width / 2 + 0.3, z: center.z + size.depth / 2 - 0.32 },
  ];
}

function pointKey(point: VoxelPoint): string {
  return `${point.x}:${point.z}`;
}
