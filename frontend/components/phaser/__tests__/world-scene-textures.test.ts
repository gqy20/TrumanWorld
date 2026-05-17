import type { SceneAgent, SceneLocation } from "@/lib/world-scene-adapter";

import {
  createPixelTextures,
  ensureAgentTexture,
  ensureGroundTexture,
  ensureLocationTexture,
} from "../world-scene-textures";

jest.mock("phaser", () => ({
  Display: {
    Color: {
      IntegerToColor: jest.fn((color: number) => ({
        color,
        darken: jest.fn(() => ({ color: color - 1 })),
        lighten: jest.fn(() => ({ color: color + 1 })),
      })),
    },
  },
}));

function makeGraphics() {
  return {
    fillStyle: jest.fn().mockReturnThis(),
    fillRect: jest.fn().mockReturnThis(),
    lineStyle: jest.fn().mockReturnThis(),
    strokeRect: jest.fn().mockReturnThis(),
    generateTexture: jest.fn().mockReturnThis(),
    destroy: jest.fn(),
  };
}

function makeScene(existingTextures: string[] = []) {
  const graphics = makeGraphics();
  return {
    textures: {
      exists: jest.fn((key: string) => existingTextures.includes(key)),
    },
    make: {
      graphics: jest.fn(() => graphics),
    },
    graphics,
  };
}

describe("world scene texture helpers", () => {
  it("returns existing ground texture keys without regenerating", () => {
    const scene = makeScene(["pixel-ground-lawn"]);

    expect(ensureGroundTexture(scene as never, "lawn")).toBe("pixel-ground-lawn");
    expect(scene.make.graphics).not.toHaveBeenCalled();
  });

  it("generates missing ground textures", () => {
    const scene = makeScene();

    expect(ensureGroundTexture(scene as never, "plaza")).toBe("pixel-ground-plaza");
    expect(scene.graphics.generateTexture).toHaveBeenCalledWith("pixel-ground-plaza", 32, 32);
    expect(scene.graphics.destroy).toHaveBeenCalled();
  });

  it("generates missing location and agent textures", () => {
    const scene = makeScene();
    const location: SceneLocation = {
      id: "loc-1",
      name: "Cafe",
      locationType: "cafe",
      visual: { visualPreset: "shop" },
      x: 0,
      y: 0,
      capacity: 4,
      occupantCount: 0,
      heat: 0,
    };
    const agent: SceneAgent = {
      id: "agent-1",
      name: "Mei",
      locationId: "loc-1",
      status: "talking",
      slotIndex: 0,
      visual: { visualPreset: "student" },
    };

    ensureLocationTexture(scene as never, location);
    ensureAgentTexture(scene as never, agent);

    expect(scene.graphics.generateTexture).toHaveBeenCalledWith("pixel-building-shop-cafe", 24, 24);
    expect(scene.graphics.generateTexture).toHaveBeenCalledWith("pixel-agent-student-talking", 16, 16);
  });

  it("creates baseline pixel textures when missing", () => {
    const scene = makeScene();

    createPixelTextures(scene as never);

    expect(scene.textures.exists).toHaveBeenCalledWith("pixel-ground");
    expect(scene.graphics.generateTexture).toHaveBeenCalledWith("pixel-ground", 32, 32);
    expect(scene.graphics.generateTexture).toHaveBeenCalledWith("pixel-agent-idle", 16, 16);
    expect(scene.graphics.generateTexture).toHaveBeenCalledWith("pixel-agent-student-working", 16, 16);
  });
});
