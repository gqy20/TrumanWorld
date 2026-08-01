import type { SceneLocation, SceneNavigation } from "@/lib/world-scene-adapter";

import type { VoxelPlot, VoxelPoint, VoxelSize } from "./types";
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
        agentAnchors: buildAgentAnchors(entrance),
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

function buildAgentAnchors(entrance: VoxelPoint): VoxelPoint[] {
  return [-0.42, -0.14, 0.14, 0.42, -0.28, 0.28].map((offset, index) => ({
    x: entrance.x + offset,
    z: entrance.z + (index >= 4 ? 0.28 : 0),
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
