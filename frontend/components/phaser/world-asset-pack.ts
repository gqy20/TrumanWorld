import type * as Phaser from "phaser";

import type { SceneAgent, SceneLocation } from "@/lib/world-scene-adapter";

export const TOWN_ASSET_PACK_ID = "default-town";
export const TOWN_ASSET_PACK_BASE_URL = `/world-assets/${TOWN_ASSET_PACK_ID}`;
export const TOWN_SPRITESHEET_KEY = `world-assets-${TOWN_ASSET_PACK_ID}`;
export const TOWN_MANIFEST_KEY = `world-assets-${TOWN_ASSET_PACK_ID}-manifest`;
export const TOWN_FRAME_WIDTH = 128;
export const TOWN_FRAME_HEIGHT = 128;

export type TownAssetTimelineFrame = {
  sprite: number;
  duration: number;
};

export type TownAssetFrameSpec = {
  frame: number;
  anchor?: [number, number];
  display?: [number, number];
};

export type TownAssetPackManifest = {
  schemaVersion: number;
  sprite: {
    image: string;
    frameWidth: number;
    frameHeight: number;
    columns: number;
    rows: number;
    frameCount: number;
  };
  buildings?: Record<string, TownAssetFrameSpec>;
  tiles?: Record<string, TownAssetFrameSpec>;
  props?: Record<string, TownAssetFrameSpec>;
  agents?: Partial<Record<SceneAgent["status"], TownAssetTimelineFrame[]>>;
};

const LOCATION_FRAMES: Record<string, number> = {
  home: 0,
  dorm: 0,
  cafe: 1,
  shop: 1,
  office: 2,
  tower: 2,
  library: 3,
  hall: 3,
  lecture_hall: 3,
  plaza: 4,
  square: 4,
  park: 5,
  grove: 5,
  quad: 5,
};

const AGENT_FRAMES: Record<SceneAgent["status"], number> = {
  idle: 16,
  moving: 17,
  talking: 18,
  working: 19,
  resting: 20,
};

const TILE_FALLBACKS: Record<string, TownAssetFrameSpec> = {
  roadStraight: { frame: 7, anchor: [0.5, 0.5], display: [78, 38] },
  roadCross: { frame: 8, anchor: [0.5, 0.5], display: [78, 38] },
  roadBend: { frame: 9, anchor: [0.5, 0.5], display: [78, 38] },
};

const PROP_FALLBACKS: Record<string, TownAssetFrameSpec> = {
  tree: { frame: 10, anchor: [0.5, 0.9], display: [54, 68] },
  lamp: { frame: 11, anchor: [0.5, 0.95], display: [28, 56] },
  bench: { frame: 12, anchor: [0.5, 0.78], display: [48, 32] },
  flowers: { frame: 13, anchor: [0.5, 0.76], display: [36, 26] },
  shrub: { frame: 14, anchor: [0.5, 0.8], display: [40, 30] },
};

export function preloadTownAssetPack(scene: Phaser.Scene): void {
  scene.load.json(TOWN_MANIFEST_KEY, `${TOWN_ASSET_PACK_BASE_URL}/manifest.json`);
  scene.load.spritesheet(TOWN_SPRITESHEET_KEY, `${TOWN_ASSET_PACK_BASE_URL}/spritesheet.webp`, {
    frameWidth: TOWN_FRAME_WIDTH,
    frameHeight: TOWN_FRAME_HEIGHT,
  });
}

export function getTownAssetPackManifest(scene: Phaser.Scene): TownAssetPackManifest | null {
  const cache = scene.cache as Phaser.Cache.CacheManager | undefined;
  const manifest = cache?.json?.get(TOWN_MANIFEST_KEY) as TownAssetPackManifest | undefined;
  return manifest ?? null;
}

export function getLocationAssetFrame(
  location: SceneLocation,
  manifest?: TownAssetPackManifest | null,
): number {
  const visualPreset = location.visual.visualPreset;
  const assetKey = resolveLocationAssetKey(visualPreset ?? location.locationType);
  return manifest?.buildings?.[assetKey]?.frame ?? LOCATION_FRAMES[assetKey] ?? 6;
}

export function getAgentAssetFrame(
  agent: SceneAgent,
  manifest?: TownAssetPackManifest | null,
  nowMs = 0,
): number {
  const timeline = manifest?.agents?.[agent.status];
  if (timeline?.length) {
    return resolveTimelineFrame(timeline, nowMs);
  }
  return AGENT_FRAMES[agent.status] ?? AGENT_FRAMES.idle;
}

export function getTownTileAssetSpec(
  key: string,
  manifest?: TownAssetPackManifest | null,
): TownAssetFrameSpec {
  return manifest?.tiles?.[key] ?? TILE_FALLBACKS[key] ?? TILE_FALLBACKS.roadStraight;
}

export function getTownPropAssetSpec(
  key: string,
  manifest?: TownAssetPackManifest | null,
): TownAssetFrameSpec {
  return manifest?.props?.[key] ?? PROP_FALLBACKS[key] ?? PROP_FALLBACKS.shrub;
}

export function resolveTimelineFrame(timeline: TownAssetTimelineFrame[], nowMs: number): number {
  const duration = timeline.reduce((sum, frame) => sum + Math.max(0, frame.duration), 0);
  if (duration <= 0) {
    return timeline[0]?.sprite ?? 0;
  }

  let elapsed = nowMs % duration;
  for (const frame of timeline) {
    const frameDuration = Math.max(0, frame.duration);
    if (elapsed < frameDuration) {
      return frame.sprite;
    }
    elapsed -= frameDuration;
  }
  return timeline[timeline.length - 1]?.sprite ?? 0;
}

function resolveLocationAssetKey(locationType: string): string {
  switch (locationType) {
    case "dorm":
      return "home";
    case "shop":
      return "cafe";
    case "tower":
      return "office";
    case "hall":
    case "lecture_hall":
      return "library";
    case "square":
      return "plaza";
    case "grove":
    case "quad":
      return "park";
    default:
      return locationType;
  }
}
