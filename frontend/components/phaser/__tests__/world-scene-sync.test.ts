import type { SceneAgent, SceneLocation } from "@/lib/world-scene-adapter";

import { syncAgents, syncLocations, type AgentNode, type LocationNode } from "../world-scene-sync";

jest.mock("phaser", () => ({
  Math: {
    DegToRad: jest.fn((degrees: number) => degrees * (globalThis.Math.PI / 180)),
  },
}));

type MockGameObject = {
  __handlers: Record<string, () => void>;
  alpha: number;
  x: number;
  y: number;
  text: string;
  texture: string;
  destroy: jest.Mock;
  setAlpha: jest.Mock;
  setDepth: jest.Mock;
  setDisplaySize: jest.Mock;
  setFillStyle: jest.Mock;
  setInteractive: jest.Mock;
  setOrigin: jest.Mock;
  setPosition: jest.Mock;
  setScale: jest.Mock;
  setText: jest.Mock;
  setTexture: jest.Mock;
  on: jest.Mock;
};

function mockGameObject(x = 0, y = 0, text = "", texture = ""): MockGameObject {
  const handlers: Record<string, () => void> = {};
  const object: MockGameObject = {
    __handlers: handlers,
    alpha: 1,
    x,
    y,
    text,
    texture,
    destroy: jest.fn(),
    setAlpha: jest.fn().mockImplementation((alpha: number) => {
      object.alpha = alpha;
      return object;
    }),
    setDepth: jest.fn().mockReturnThis(),
    setDisplaySize: jest.fn().mockReturnThis(),
    setFillStyle: jest.fn().mockReturnThis(),
    setInteractive: jest.fn().mockReturnThis(),
    setOrigin: jest.fn().mockReturnThis(),
    setPosition: jest.fn().mockImplementation((nextX: number, nextY: number) => {
      object.x = nextX;
      object.y = nextY;
      return object;
    }),
    setScale: jest.fn().mockReturnThis(),
    setText: jest.fn().mockImplementation((nextText: string) => {
      object.text = nextText;
      return object;
    }),
    setTexture: jest.fn().mockImplementation((nextTexture: string) => {
      object.texture = nextTexture;
      return object;
    }),
    on: jest.fn().mockImplementation((eventName: string, handler: () => void) => {
      handlers[eventName] = handler;
      return object;
    }),
  };
  return object;
}

function mockScene() {
  return {
    add: {
      circle: jest.fn((x: number, y: number) => mockGameObject(x, y)),
      image: jest.fn((x: number, y: number, texture: string) => mockGameObject(x, y, "", texture)),
      text: jest.fn((x: number, y: number, text: string) => mockGameObject(x, y, text)),
    },
    events: {
      emit: jest.fn(),
    },
    tweens: {
      add: jest.fn(() => ({ stop: jest.fn() })),
    },
  };
}

function location(overrides: Partial<SceneLocation> = {}): SceneLocation {
  return {
    id: "loc-1",
    name: "Cafe",
    locationType: "cafe",
    visual: { visualPreset: "shop", glyph: "C" },
    x: 10,
    y: 20,
    capacity: 6,
    occupantCount: 2,
    heat: 0.1,
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

function syncContext(scene: ReturnType<typeof mockScene>) {
  return {
    scene: scene as never,
    ensureLocationTexture: jest.fn(),
    ensureAgentTexture: jest.fn(),
    mapWorldToCanvas: jest.fn((x: number, y: number) => ({ x: x * 10, y: y * 10 })),
    getAgentPosition: jest.fn((targetLocation: SceneLocation, slotIndex: number) => ({
      x: targetLocation.x * 10 + slotIndex * 12,
      y: targetLocation.y * 10 + 30,
    })),
    playTapFeedback: jest.fn(),
    showTooltip: jest.fn(),
    hideTooltip: jest.fn(),
  };
}

describe("world scene sync helpers", () => {
  it("creates, updates, clicks, and removes location nodes", () => {
    const scene = mockScene();
    const context = syncContext(scene);
    const nodes = new Map<string, LocationNode>();

    syncLocations(context, nodes, [
      location(),
      location({ id: "loc-2", name: "Library", locationType: "library", x: 30, y: 40 }),
    ]);

    expect(nodes.size).toBe(2);
    expect(scene.add.image).toHaveBeenCalledTimes(2);
    expect(context.ensureLocationTexture).toHaveBeenCalledTimes(2);

    const cafe = nodes.get("loc-1");
    const cafeBody = cafe?.body as unknown as MockGameObject;
    expect(cafeBody.x).toBe(100);
    expect(cafeBody.y).toBe(200);
    expect(cafe?.label.text).toBe("Cafe");
    expect(cafe?.badge.text).toBe("2/6");

    cafeBody.__handlers.pointerdown();
    cafeBody.__handlers.pointerover();
    cafeBody.__handlers.pointerout();

    expect(context.playTapFeedback).toHaveBeenCalledWith(cafe?.body, cafe?.icon, cafe?.label, cafe?.badge);
    expect(scene.events.emit).toHaveBeenCalledWith("location:click", "loc-1");
    expect(context.showTooltip).toHaveBeenCalledWith(100, 152, "Cafe / cafe");
    expect(context.hideTooltip).toHaveBeenCalled();

    const library = nodes.get("loc-2");
    syncLocations(context, nodes, [
      location({
        name: "Campus Cafe",
        x: 12,
        y: 22,
        capacity: 8,
        occupantCount: 5,
        heat: 0.4,
        visual: { visualPreset: "market", glyph: "M" },
      }),
    ]);

    expect(nodes.size).toBe(1);
    expect(library?.body.destroy).toHaveBeenCalled();
    expect(library?.label.destroy).toHaveBeenCalled();
    expect(cafe?.body.setPosition).toHaveBeenCalledWith(120, 220);
    expect(cafe?.label.setText).toHaveBeenCalledWith("Campus Cafe");
    expect(cafe?.badge.setText).toHaveBeenCalledWith("5/8");
  });

  it("syncs agent coordinates, skips missing locations, and removes stale agents", () => {
    const scene = mockScene();
    const context = syncContext(scene);
    const nodes = new Map<string, AgentNode>();
    const locations = [
      location(),
      location({ id: "loc-2", name: "Library", x: 30, y: 40 }),
    ];

    syncAgents(context, nodes, [
      agent({ visual: { visualPreset: "student", marker: "M" } }),
      agent({ id: "missing-location", locationId: "unknown" }),
    ], locations);

    expect(nodes.size).toBe(1);
    expect(scene.add.image).toHaveBeenCalledTimes(1);
    expect(context.ensureAgentTexture).toHaveBeenCalledWith(
      expect.objectContaining({ id: "agent-1" }),
    );
    expect(context.ensureAgentTexture).not.toHaveBeenCalledWith(
      expect.objectContaining({ id: "missing-location" }),
    );

    const mei = nodes.get("agent-1");
    const meiBody = mei?.body as unknown as MockGameObject;
    expect(meiBody.x).toBe(100);
    expect(meiBody.y).toBe(230);
    expect(mei?.marker.text).toBe("M");
    expect(mei?.label.text).toBe("Mei");

    meiBody.__handlers.pointerdown();
    meiBody.__handlers.pointerover();
    meiBody.__handlers.pointerout();

    expect(context.playTapFeedback).toHaveBeenCalledWith(mei?.body, mei?.marker, mei?.label);
    expect(scene.events.emit).toHaveBeenCalledWith("agent:click", "agent-1");
    expect(context.showTooltip).toHaveBeenCalledWith(100, 196, "Mei / idle");
    expect(context.hideTooltip).toHaveBeenCalled();

    syncAgents(context, nodes, [
      agent({
        name: "Mei Lin",
        locationId: "loc-2",
        status: "talking",
        slotIndex: 2,
        visual: { visualPreset: "student", marker: "!" },
      }),
    ], locations);

    expect(scene.add.image).toHaveBeenCalledTimes(1);
    expect(scene.tweens.add).toHaveBeenCalledWith(
      expect.objectContaining({
        targets: mei?.body,
        x: 324,
        y: 430,
      }),
    );
    expect(mei?.body.setTexture).toHaveBeenCalledWith("pixel-agent-student-talking");
    expect(mei?.marker.setText).toHaveBeenCalledWith("!");
    expect(mei?.label.setText).toHaveBeenCalledWith("Mei Lin");

    syncAgents(context, nodes, [], locations);

    expect(nodes.size).toBe(0);
    expect(mei?.body.destroy).toHaveBeenCalled();
    expect(mei?.marker.destroy).toHaveBeenCalled();
    expect(mei?.label.destroy).toHaveBeenCalled();
  });
});
