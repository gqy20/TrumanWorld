import type { SceneLocation } from "@/lib/world-scene-adapter";

import type { VoxelDistrict, VoxelPlot, VoxelPoint, VoxelSize } from "./types";

type PlotTemplate = {
  center: VoxelPoint;
  district: VoxelDistrict;
  size: VoxelSize;
  footprint: VoxelSize;
  entranceSide: "north" | "east" | "south" | "west";
};

const PLOT_TEMPLATES: Record<string, PlotTemplate> = {
  home: plot(-3, 3, "home", "south"),
  dorm: plot(-4.8, 4.2, "home", "south"),
  cafe: plot(0, 4.2, "commerce", "south"),
  shop: plot(3.2, 4.2, "commerce", "south"),
  plaza: plot(0, 0, "center", "south", { width: 2.8, depth: 2.8 }, { width: 1.2, depth: 1.2 }),
  square: plot(0, 0, "center", "south", { width: 2.8, depth: 2.8 }, { width: 1.2, depth: 1.2 }),
  office: plot(4.3, -0.9, "civic", "west", { width: 2.6, depth: 2.6 }, { width: 1.5, depth: 1.5 }),
  library: plot(2.2, -4.2, "civic", "south", { width: 2.8, depth: 2.8 }, { width: 1.7, depth: 1.5 }),
  lecture_hall: plot(5.2, -4.2, "civic", "south", { width: 2.8, depth: 2.8 }, { width: 1.8, depth: 1.5 }),
  park: plot(-4.3, -1.9, "green", "east", { width: 2.8, depth: 2.8 }, { width: 0.8, depth: 0.8 }),
  grove: plot(-5.2, -4.2, "green", "east", { width: 2.8, depth: 2.8 }, { width: 0.8, depth: 0.8 }),
  quad: plot(-2.2, -2.4, "green", "east", { width: 2.8, depth: 2.8 }, { width: 0.8, depth: 0.8 }),
};

const FALLBACK_TEMPLATES: PlotTemplate[] = [
  plot(-2.2, 2.4, "home", "south"),
  plot(2.2, 2.4, "commerce", "south"),
  plot(-2.2, -3.6, "green", "east"),
  plot(4.6, 1.6, "civic", "west"),
  plot(-5.4, 1.4, "home", "east"),
  plot(5.4, -2.4, "civic", "west"),
];

export function buildVoxelPlots(locations: SceneLocation[]): VoxelPlot[] {
  const sortedLocations = locations.slice().sort((left, right) => left.id.localeCompare(right.id));
  return sortedLocations.map((location, index) => {
    const template = resolveTemplate(location, index);
    const duplicateOffset = resolveDuplicateOffset(location, sortedLocations);
    const center = {
      x: template.center.x + duplicateOffset.x,
      z: template.center.z + duplicateOffset.z,
    };
    return {
      id: `plot-${location.id}`,
      locationId: location.id,
      locationType: location.locationType,
      district: template.district,
      center,
      size: template.size,
      footprint: template.footprint,
      entrance: resolveEntrance(center, template.size, template.entranceSide),
      agentAnchors: buildAgentAnchors(center, template.size, template.entranceSide),
      decorationAnchors: buildDecorationAnchors(center, template.size),
      source: location,
    };
  });
}

export function findPlotForLocation(plots: VoxelPlot[], locationId: string): VoxelPlot | undefined {
  return plots.find((plotItem) => plotItem.locationId === locationId);
}

function plot(
  x: number,
  z: number,
  district: VoxelDistrict,
  entranceSide: PlotTemplate["entranceSide"],
  size: VoxelSize = { width: 2.4, depth: 2.4 },
  footprint: VoxelSize = { width: 1.35, depth: 1.35 },
): PlotTemplate {
  return {
    center: { x, z },
    district,
    size,
    footprint,
    entranceSide,
  };
}

function resolveTemplate(location: SceneLocation, index: number): PlotTemplate {
  const visualPreset = location.visual.visualPreset;
  return (
    PLOT_TEMPLATES[location.locationType] ??
    (visualPreset ? PLOT_TEMPLATES[visualPreset] : undefined) ??
    FALLBACK_TEMPLATES[index % FALLBACK_TEMPLATES.length]
  );
}

function resolveDuplicateOffset(location: SceneLocation, locations: SceneLocation[]): VoxelPoint {
  const sameType = locations
    .filter((candidate) => candidate.locationType === location.locationType)
    .sort((left, right) => left.id.localeCompare(right.id));
  const duplicateIndex = sameType.findIndex((candidate) => candidate.id === location.id);
  if (duplicateIndex <= 0) {
    return { x: 0, z: 0 };
  }
  const offsets = [
    { x: -2.8, z: 0 },
    { x: 0, z: 2.8 },
    { x: 2.8, z: 0 },
    { x: 0, z: -2.8 },
  ];
  return offsets[(duplicateIndex - 1) % offsets.length];
}

function resolveEntrance(
  center: VoxelPoint,
  size: VoxelSize,
  side: PlotTemplate["entranceSide"],
): VoxelPoint {
  switch (side) {
    case "north":
      return { x: center.x, z: center.z - size.depth / 2 - 0.25 };
    case "east":
      return { x: center.x + size.width / 2 + 0.25, z: center.z };
    case "west":
      return { x: center.x - size.width / 2 - 0.25, z: center.z };
    case "south":
    default:
      return { x: center.x, z: center.z + size.depth / 2 + 0.25 };
  }
}

function buildAgentAnchors(
  center: VoxelPoint,
  size: VoxelSize,
  side: PlotTemplate["entranceSide"],
): VoxelPoint[] {
  const entrance = resolveEntrance(center, size, side);
  const tangent = side === "north" || side === "south" ? { x: 1, z: 0 } : { x: 0, z: 1 };
  return [-0.42, -0.14, 0.14, 0.42, -0.28, 0.28].map((offset, index) => ({
    x: entrance.x + tangent.x * offset,
    z: entrance.z + tangent.z * offset + (index >= 4 ? 0.28 : 0),
  }));
}

function buildDecorationAnchors(center: VoxelPoint, size: VoxelSize): VoxelPlot["decorationAnchors"] {
  return [
    { kind: "tree", x: center.x - size.width / 2 + 0.35, z: center.z - size.depth / 2 + 0.35 },
    { kind: "lamp", x: center.x + size.width / 2 - 0.28, z: center.z + size.depth / 2 - 0.35 },
    { kind: "flowers", x: center.x - size.width / 2 + 0.4, z: center.z + size.depth / 2 - 0.38 },
  ];
}
