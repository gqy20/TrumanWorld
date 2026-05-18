import type * as Phaser from "phaser";

import type { SceneAgent, SceneLocation } from "@/lib/world-scene-adapter";

export const TOWN_ASSET_PACK_ID = "default-town";
export const TOWN_ASSET_PACK_BASE_URL = `/world-assets/${TOWN_ASSET_PACK_ID}`;
export const TOWN_SPRITESHEET_KEY = `world-assets-${TOWN_ASSET_PACK_ID}`;
export const TOWN_MANIFEST_KEY = `world-assets-${TOWN_ASSET_PACK_ID}-manifest`;
export const TOWN_FRAME_WIDTH = 128;
export const TOWN_FRAME_HEIGHT = 128;

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

export function preloadTownAssetPack(scene: Phaser.Scene): void {
  scene.load.json(TOWN_MANIFEST_KEY, `${TOWN_ASSET_PACK_BASE_URL}/manifest.json`);
  scene.load.spritesheet(TOWN_SPRITESHEET_KEY, `${TOWN_ASSET_PACK_BASE_URL}/spritesheet.webp`, {
    frameWidth: TOWN_FRAME_WIDTH,
    frameHeight: TOWN_FRAME_HEIGHT,
  });
}

export function getLocationAssetFrame(location: SceneLocation): number {
  const visualPreset = location.visual.visualPreset;
  return LOCATION_FRAMES[visualPreset ?? ""] ?? LOCATION_FRAMES[location.locationType] ?? 6;
}

export function getAgentAssetFrame(agent: SceneAgent): number {
  return AGENT_FRAMES[agent.status] ?? AGENT_FRAMES.idle;
}
