import type { SceneAgent, SceneLocation } from "@/lib/world-scene-adapter";

import {
  TOWN_ASSET_PACK_BASE_URL,
  TOWN_FRAME_HEIGHT,
  TOWN_FRAME_WIDTH,
  TOWN_MANIFEST_KEY,
  TOWN_SPRITESHEET_KEY,
  getAgentAssetFrame,
  getLocationAssetFrame,
  preloadTownAssetPack,
  resolveTimelineFrame,
  type TownAssetPackManifest,
} from "../world-asset-pack";

function location(overrides: Partial<SceneLocation> = {}): SceneLocation {
  return {
    id: "loc-1",
    name: "Cafe",
    locationType: "cafe",
    visual: {},
    x: 0,
    y: 0,
    capacity: 4,
    occupantCount: 0,
    heat: 0,
    ...overrides,
  };
}

function agent(overrides: Partial<SceneAgent> = {}): SceneAgent {
  return {
    id: "agent-1",
    name: "Mei",
    locationId: "loc-1",
    status: "idle",
    slotIndex: 0,
    ...overrides,
  };
}

describe("world asset pack helpers", () => {
  it("preloads the default town manifest and WebP spritesheet", () => {
    const scene = {
      load: {
        json: jest.fn(),
        spritesheet: jest.fn(),
      },
    };

    preloadTownAssetPack(scene as never);

    expect(scene.load.json).toHaveBeenCalledWith(
      TOWN_MANIFEST_KEY,
      `${TOWN_ASSET_PACK_BASE_URL}/manifest.json`,
    );
    expect(scene.load.spritesheet).toHaveBeenCalledWith(
      TOWN_SPRITESHEET_KEY,
      `${TOWN_ASSET_PACK_BASE_URL}/spritesheet.webp`,
      { frameWidth: TOWN_FRAME_WIDTH, frameHeight: TOWN_FRAME_HEIGHT },
    );
  });

  it("maps semantic locations and agent statuses to spritesheet frames", () => {
    expect(getLocationAssetFrame(location({ locationType: "home" }))).toBe(0);
    expect(getLocationAssetFrame(location({ locationType: "cafe" }))).toBe(1);
    expect(getLocationAssetFrame(location({ locationType: "unknown" }))).toBe(6);

    expect(getAgentAssetFrame(agent({ status: "idle" }))).toBe(16);
    expect(getAgentAssetFrame(agent({ status: "moving" }))).toBe(17);
    expect(getAgentAssetFrame(agent({ status: "talking" }))).toBe(18);
  });

  it("uses manifest mappings and timeline durations when provided", () => {
    const manifest: TownAssetPackManifest = {
      schemaVersion: 2,
      sprite: {
        image: "spritesheet.webp",
        frameWidth: 128,
        frameHeight: 128,
        columns: 8,
        rows: 4,
        frameCount: 32,
      },
      buildings: {
        cafe: { frame: 11 },
        generic: { frame: 12 },
      },
      agents: {
        moving: [
          { sprite: 21, duration: 100 },
          { sprite: 22, duration: 200 },
        ],
      },
    };

    expect(getLocationAssetFrame(location({ locationType: "shop" }), manifest)).toBe(11);
    expect(getLocationAssetFrame(location({ locationType: "unknown" }), manifest)).toBe(6);
    expect(getAgentAssetFrame(agent({ status: "moving" }), manifest, 99)).toBe(21);
    expect(getAgentAssetFrame(agent({ status: "moving" }), manifest, 100)).toBe(22);
  });

  it("resolves timeline frames with modulo elapsed time", () => {
    expect(
      resolveTimelineFrame(
        [
          { sprite: 4, duration: 100 },
          { sprite: 5, duration: 200 },
        ],
        350,
      ),
    ).toBe(4);
  });
});
