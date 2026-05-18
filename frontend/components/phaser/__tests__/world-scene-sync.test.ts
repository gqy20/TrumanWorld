import type { SceneAgent, SceneLocation, SceneWorld } from "@/lib/world-scene-adapter";

import { TOWN_SPRITESHEET_KEY, getAgentAssetFrame } from "../world-asset-pack";
import {
  syncAgents,
  syncBubbles,
  syncLocations,
  syncMoveTrails,
  refreshAgentAnimationFrames,
  type AgentNode,
  type BubbleNode,
  type LocationNode,
  type TrailNode,
} from "../world-scene-sync";

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
  setLineWidth: jest.Mock;
  setOrigin: jest.Mock;
  setPosition: jest.Mock;
  setRotation: jest.Mock;
  setScale: jest.Mock;
  setSize: jest.Mock;
  setStrokeStyle: jest.Mock;
  setText: jest.Mock;
  setTexture: jest.Mock;
  setTo: jest.Mock;
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
    setLineWidth: jest.fn().mockReturnThis(),
    setOrigin: jest.fn().mockReturnThis(),
    setPosition: jest.fn().mockImplementation((nextX: number, nextY: number) => {
      object.x = nextX;
      object.y = nextY;
      return object;
    }),
    setRotation: jest.fn().mockReturnThis(),
    setScale: jest.fn().mockReturnThis(),
    setSize: jest.fn().mockReturnThis(),
    setStrokeStyle: jest.fn().mockReturnThis(),
    setText: jest.fn().mockImplementation((nextText: string) => {
      object.text = nextText;
      return object;
    }),
    setTexture: jest.fn().mockImplementation((nextTexture: string) => {
      object.texture = nextTexture;
      return object;
    }),
    setTo: jest.fn().mockReturnThis(),
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
      line: jest.fn(() => mockGameObject()),
      rectangle: jest.fn((x: number, y: number) => mockGameObject(x, y)),
      text: jest.fn((x: number, y: number, text: string) => mockGameObject(x, y, text)),
      triangle: jest.fn((x: number, y: number) => mockGameObject(x, y)),
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
    nowMs: 100,
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

function world(overrides: Partial<SceneWorld> = {}): SceneWorld {
  return {
    runId: "run-1",
    locations: [
      location(),
      location({ id: "loc-2", name: "Library", locationType: "library", x: 30, y: 40 }),
    ],
    agents: [
      agent({ visual: { visualPreset: "student", marker: "M" } }),
    ],
    moveTrails: [],
    bubbles: [],
    ambience: {
      label: "上午",
      overlayColor: "rgba(255,255,255,0)",
      isDark: false,
    },
    stage: {},
    ...overrides,
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
    expect(cafeBody.y).toBe(172);
    expect(cafe?.label.text).toBe("Cafe");
    expect(cafe?.badge.text).toBe("2/6");
    expect(cafe?.label.alpha).toBe(0);
    expect(cafe?.badge.alpha).toBe(0);

    cafeBody.__handlers.pointerdown();
    cafeBody.__handlers.pointerover();
    expect(cafe?.label.alpha).toBe(1);
    expect(cafe?.badge.alpha).toBe(1);
    cafeBody.__handlers.pointerout();
    expect(cafe?.label.alpha).toBe(0);
    expect(cafe?.badge.alpha).toBe(0);

    expect(context.playTapFeedback).toHaveBeenCalledWith(cafe?.body, cafe?.icon, cafe?.label, cafe?.badge);
    expect(scene.events.emit).toHaveBeenCalledWith("location:click", "loc-1");
    expect(context.showTooltip).toHaveBeenCalledWith(100, 108, "Cafe / cafe");
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
    expect(cafe?.body.setPosition).toHaveBeenCalledWith(120, 192);
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
    expect(mei?.body.setTexture).toHaveBeenCalledWith(
      TOWN_SPRITESHEET_KEY,
      getAgentAssetFrame(agent({ status: "talking" })),
    );
    expect(mei?.marker.setText).toHaveBeenCalledWith("!");
    expect(mei?.label.setText).toHaveBeenCalledWith("Mei Lin");

    syncAgents(context, nodes, [], locations);

    expect(nodes.size).toBe(0);
    expect(mei?.body.destroy).toHaveBeenCalled();
    expect(mei?.marker.destroy).toHaveBeenCalled();
    expect(mei?.label.destroy).toHaveBeenCalled();
  });

  it("refreshes agent animation frames from the manifest timeline", () => {
    const nodes = new Map<string, AgentNode>();
    const body = mockGameObject();
    nodes.set("agent-1", {
      body: body as never,
      marker: mockGameObject() as never,
      label: mockGameObject() as never,
      status: "moving",
    });

    refreshAgentAnimationFrames(nodes, {
      schemaVersion: 2,
      sprite: {
        image: "spritesheet.webp",
        frameWidth: 128,
        frameHeight: 128,
        columns: 8,
        rows: 4,
        frameCount: 32,
      },
      agents: {
        moving: [
          { sprite: 21, duration: 100 },
          { sprite: 22, duration: 100 },
        ],
      },
    }, 150);

    expect(body.setTexture).toHaveBeenCalledWith(TOWN_SPRITESHEET_KEY, 22);
  });

  it("creates, updates, skips invalid, and removes move trail nodes", () => {
    const scene = mockScene();
    const context = syncContext(scene);
    const nodes = new Map<string, TrailNode>();
    const sceneWorld = world({
      moveTrails: [
        {
          id: "trail-1",
          actorId: "agent-1",
          actorName: "Mei",
          fromLocationId: "loc-1",
          toLocationId: "loc-2",
          recencyIndex: 0,
        },
        {
          id: "invalid-trail",
          actorName: "Nobody",
          fromLocationId: "unknown",
          toLocationId: "loc-2",
          recencyIndex: 1,
        },
      ],
    });

    syncMoveTrails(context, nodes, sceneWorld);

    expect(nodes.size).toBe(1);
    expect(scene.add.line).toHaveBeenCalledTimes(1);
    expect(scene.add.triangle).toHaveBeenCalledTimes(1);
    expect(scene.add.text).toHaveBeenCalledWith(
      200,
      282,
      "Mei →",
      expect.objectContaining({ color: "#7dd3fc" }),
    );

    const trail = nodes.get("trail-1");
    expect(trail?.line.setAlpha).toHaveBeenCalledWith(0.68);
    expect(trail?.arrow.setRotation).toHaveBeenCalledWith(expect.any(Number));
    expect(scene.tweens.add).toHaveBeenCalledWith(
      expect.objectContaining({
        targets: [trail?.line, trail?.arrow, trail?.label],
        repeat: -1,
      }),
    );

    syncMoveTrails(context, nodes, world({
      moveTrails: [
        {
          id: "trail-1",
          actorId: "agent-1",
          actorName: "Mei Lin",
          fromLocationId: "loc-2",
          toLocationId: "loc-1",
          recencyIndex: 2,
        },
      ],
    }));

    expect(scene.add.line).toHaveBeenCalledTimes(1);
    expect(trail?.line.setTo).toHaveBeenCalledWith(300, 400, 100, 200);
    expect(trail?.label.setText).toHaveBeenCalledWith("Mei Lin →");
    expect(trail?.label.setAlpha).toHaveBeenCalledWith(0.4);

    syncMoveTrails(context, nodes, world({ moveTrails: [] }));

    expect(nodes.size).toBe(0);
    expect(trail?.line.destroy).toHaveBeenCalled();
    expect(trail?.arrow.destroy).toHaveBeenCalled();
    expect(trail?.label.destroy).toHaveBeenCalled();
  });

  it("anchors bubbles to speaking agents, falls back to locations, and removes stale bubbles", () => {
    const scene = mockScene();
    const context = syncContext(scene);
    const nodes = new Map<string, BubbleNode>();
    const sceneWorld = world({
      bubbles: [
        {
          id: "bubble-agent",
          text: "hello",
          speakerAgentId: "agent-1",
          speakerName: "Mei",
          locationId: "loc-1",
          recencyIndex: 0,
        },
        {
          id: "bubble-location",
          text: "announcement",
          speakerName: "Narrator",
          locationId: "loc-2",
          recencyIndex: 1,
        },
        {
          id: "bubble-invalid",
          text: "lost",
          speakerName: "Nobody",
          locationId: "unknown",
          recencyIndex: 0,
        },
      ],
    });

    syncBubbles(context, nodes, sceneWorld);

    expect(nodes.size).toBe(2);
    expect(scene.add.rectangle).toHaveBeenCalledTimes(2);
    expect(scene.add.text).toHaveBeenCalledWith(
      150,
      176,
      "Mei: hello",
      expect.objectContaining({ color: "#0f172a" }),
    );
    expect(scene.add.text).toHaveBeenCalledWith(
      300,
      328,
      "Narrator: announcement",
      expect.objectContaining({ color: "#0f172a" }),
    );

    const agentBubble = nodes.get("bubble-agent");
    const locationBubble = nodes.get("bubble-location");
    expect(agentBubble?.box.setStrokeStyle).toHaveBeenCalledWith(1, 0xcbd5e1, 0.9);
    expect(scene.tweens.add).toHaveBeenCalledWith(
      expect.objectContaining({
        targets: [agentBubble?.box, agentBubble?.text],
        repeat: -1,
      }),
    );

    syncBubbles(context, nodes, world({
      bubbles: [
        {
          id: "bubble-agent",
          text: "updated text",
          speakerAgentId: "agent-1",
          speakerName: "Mei",
          locationId: "loc-1",
          recencyIndex: 2,
        },
      ],
    }));

    expect(nodes.size).toBe(1);
    expect(scene.add.rectangle).toHaveBeenCalledTimes(2);
    expect(agentBubble?.box.setPosition).toHaveBeenCalledWith(150, 140);
    expect(agentBubble?.box.setSize).toHaveBeenCalledWith(98.6, 24);
    expect(agentBubble?.text.setText).toHaveBeenCalledWith("Mei: updated text");
    expect(locationBubble?.box.destroy).toHaveBeenCalled();
    expect(locationBubble?.text.destroy).toHaveBeenCalled();

    syncBubbles(context, nodes, world({ bubbles: [] }));

    expect(nodes.size).toBe(0);
    expect(agentBubble?.box.destroy).toHaveBeenCalled();
    expect(agentBubble?.text.destroy).toHaveBeenCalled();
  });
});
