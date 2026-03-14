"use client";

export type ProjectedPoint = {
  x: number;
  y: number;
};

export type BuildingFootprint = {
  width: number;
  depth: number;
  height: number;
};

const ISO_CENTER_X = 350;
const ISO_ORIGIN_Y = 92;
const ISO_TILE_WIDTH = 470;
const ISO_TILE_HEIGHT = 200;

const BASE_FOOTPRINTS: Record<string, BuildingFootprint> = {
  cafe: { width: 68, depth: 42, height: 34 },
  plaza: { width: 92, depth: 58, height: 18 },
  park: { width: 104, depth: 72, height: 16 },
  shop: { width: 74, depth: 46, height: 36 },
  home: { width: 72, depth: 48, height: 38 },
  office: { width: 76, depth: 50, height: 52 },
  hospital: { width: 88, depth: 54, height: 42 },
  default: { width: 70, depth: 44, height: 32 },
};

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

export function projectToIsometric(normalizedX: number, normalizedY: number): ProjectedPoint {
  const x = ISO_CENTER_X + (normalizedX - normalizedY) * (ISO_TILE_WIDTH / 2);
  const y = ISO_ORIGIN_Y + (normalizedX + normalizedY) * (ISO_TILE_HEIGHT / 2);
  return { x, y };
}

export function getBuildingFootprint(
  locationType: string,
  capacity: number,
  heat: number,
): BuildingFootprint {
  const base = BASE_FOOTPRINTS[locationType] ?? BASE_FOOTPRINTS.default;
  const capacityScale = clamp(capacity / 8, 0, 1.8);
  const heatLift = clamp(heat * 10, 0, 8);

  return {
    width: base.width + capacityScale * 10,
    depth: base.depth + capacityScale * 7,
    height: base.height + capacityScale * 8 + heatLift,
  };
}

export function getFrontArcPosition(
  centerX: number,
  centerY: number,
  footprint: BuildingFootprint,
  index: number,
  total: number,
): ProjectedPoint {
  const safeTotal = Math.max(total, 1);
  const spread = safeTotal === 1 ? 0 : index / (safeTotal - 1) - 0.5;
  const laneWidth = Math.min(footprint.width * 0.7, 60);
  // botMid（前底点）= centerY + depth/2，小人再往前偏移一段距离确保在建筑前方
  const frontEdgeY = centerY + footprint.depth / 2;
  const x = centerX + spread * laneWidth;
  const y = frontEdgeY + Math.abs(spread) * 8 + 14;
  return { x, y };
}

export function sortByRenderOrder<T extends { svgY: number }>(nodes: T[]): T[] {
  return [...nodes].sort((left, right) => left.svgY - right.svgY);
}
