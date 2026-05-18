import type { SceneLocation } from "@/lib/world-scene-adapter";

import {
  ISO_ORIGIN_X,
  ISO_ORIGIN_Y,
  ISO_TILE_HEIGHT,
  ISO_TILE_WIDTH,
} from "./world-scene-style";

export type TownLayoutSlot = {
  tileX: number;
  tileY: number;
  entranceOffsetX: number;
  entranceOffsetY: number;
  district: "home" | "center" | "commerce" | "civic" | "green";
};

const TYPE_LAYOUT: Record<string, TownLayoutSlot> = {
  home: { tileX: 1, tileY: 5, entranceOffsetX: 0, entranceOffsetY: 24, district: "home" },
  dorm: { tileX: 1, tileY: 6, entranceOffsetX: 0, entranceOffsetY: 24, district: "home" },
  cafe: { tileX: 3, tileY: 6, entranceOffsetX: 0, entranceOffsetY: 24, district: "commerce" },
  shop: { tileX: 5, tileY: 6, entranceOffsetX: 0, entranceOffsetY: 24, district: "commerce" },
  plaza: { tileX: 3, tileY: 3, entranceOffsetX: 0, entranceOffsetY: 18, district: "center" },
  square: { tileX: 3, tileY: 3, entranceOffsetX: 0, entranceOffsetY: 18, district: "center" },
  office: { tileX: 6, tileY: 3, entranceOffsetX: 0, entranceOffsetY: 26, district: "civic" },
  library: { tileX: 5, tileY: 1, entranceOffsetX: 0, entranceOffsetY: 26, district: "civic" },
  lecture_hall: { tileX: 6, tileY: 1, entranceOffsetX: 0, entranceOffsetY: 26, district: "civic" },
  park: { tileX: 1, tileY: 2, entranceOffsetX: 0, entranceOffsetY: 20, district: "green" },
  grove: { tileX: 1, tileY: 1, entranceOffsetX: 0, entranceOffsetY: 20, district: "green" },
  quad: { tileX: 2, tileY: 2, entranceOffsetX: 0, entranceOffsetY: 20, district: "green" },
};

const FALLBACK_SLOTS: TownLayoutSlot[] = [
  { tileX: 2, tileY: 5, entranceOffsetX: 0, entranceOffsetY: 24, district: "home" },
  { tileX: 4, tileY: 5, entranceOffsetX: 0, entranceOffsetY: 24, district: "commerce" },
  { tileX: 2, tileY: 1, entranceOffsetX: 0, entranceOffsetY: 24, district: "green" },
  { tileX: 6, tileY: 4, entranceOffsetX: 0, entranceOffsetY: 24, district: "civic" },
  { tileX: 0, tileY: 4, entranceOffsetX: 0, entranceOffsetY: 24, district: "home" },
  { tileX: 7, tileY: 3, entranceOffsetX: 0, entranceOffsetY: 24, district: "civic" },
];

export function resolveTownLayout(location: SceneLocation, locations: SceneLocation[]): TownLayoutSlot {
  const typedSlot = TYPE_LAYOUT[location.locationType];
  if (typedSlot) {
    return spreadDuplicateSlot(typedSlot, location, locations);
  }

  const sortedLocations = locations.slice().sort((left, right) => left.id.localeCompare(right.id));
  const index = Math.max(0, sortedLocations.findIndex((candidate) => candidate.id === location.id));
  return FALLBACK_SLOTS[index % FALLBACK_SLOTS.length];
}

export function getTownLocationPoint(location: SceneLocation, locations: SceneLocation[]) {
  const slot = resolveTownLayout(location, locations);
  return isoTileToCanvas(slot.tileX, slot.tileY);
}

export function getTownEntrancePoint(location: SceneLocation, locations: SceneLocation[]) {
  const slot = resolveTownLayout(location, locations);
  const point = isoTileToCanvas(slot.tileX, slot.tileY);
  return {
    x: point.x + slot.entranceOffsetX,
    y: point.y + slot.entranceOffsetY,
  };
}

export function isoTileToCanvas(tileX: number, tileY: number) {
  return {
    x: Math.round(ISO_ORIGIN_X + (tileX - tileY) * (ISO_TILE_WIDTH / 2)),
    y: Math.round(ISO_ORIGIN_Y + (tileX + tileY) * (ISO_TILE_HEIGHT / 2)),
  };
}

function spreadDuplicateSlot(
  slot: TownLayoutSlot,
  location: SceneLocation,
  locations: SceneLocation[],
): TownLayoutSlot {
  const sameType = locations
    .filter((candidate) => candidate.locationType === location.locationType)
    .sort((left, right) => left.id.localeCompare(right.id));
  const duplicateIndex = sameType.findIndex((candidate) => candidate.id === location.id);
  if (duplicateIndex <= 0) {
    return slot;
  }

  const offsets = [
    { tileX: 1, tileY: 0 },
    { tileX: 0, tileY: 1 },
    { tileX: -1, tileY: 0 },
    { tileX: 0, tileY: -1 },
  ];
  const offset = offsets[(duplicateIndex - 1) % offsets.length];
  return {
    ...slot,
    tileX: clampTile(slot.tileX + offset.tileX),
    tileY: clampTile(slot.tileY + offset.tileY),
  };
}

function clampTile(value: number) {
  return Math.min(7, Math.max(0, value));
}
