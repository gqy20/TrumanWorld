import { WorldScene } from "../world-scene";

import type { SceneWorld } from "@/lib/world-scene-adapter";

jest.mock("phaser", () => ({
  Scene: class MockScene {
    createGameObject = () => {
      const handlers: Record<string, () => void> = {};
      const object: Record<string, unknown> & {
        __handlers: Record<string, () => void>;
        alpha: number;
        x: number;
        y: number;
      } = {
        __handlers: handlers,
        alpha: 1,
        x: 0,
        y: 0,
        clearTint: jest.fn().mockReturnThis(),
        setAlpha: jest.fn().mockImplementation(function (this: typeof object, alpha: number) {
          this.alpha = alpha;
          return this;
        }),
        setColor: jest.fn().mockReturnThis(),
        setDepth: jest.fn().mockReturnThis(),
        setDisplaySize: jest.fn().mockReturnThis(),
        setFillStyle: jest.fn().mockReturnThis(),
        setInteractive: jest.fn().mockReturnThis(),
        setLineWidth: jest.fn().mockReturnThis(),
        setOrigin: jest.fn().mockReturnThis(),
        setPosition: jest.fn().mockImplementation(function (this: typeof object, x: number, y: number) {
          this.x = x;
          this.y = y;
          return this;
        }),
        setRotation: jest.fn().mockReturnThis(),
        setScale: jest.fn().mockReturnThis(),
        setSize: jest.fn().mockReturnThis(),
        setStrokeStyle: jest.fn().mockReturnThis(),
        setText: jest.fn().mockReturnThis(),
        setTexture: jest.fn().mockReturnThis(),
        setTint: jest.fn().mockReturnThis(),
        setTo: jest.fn().mockReturnThis(),
        setVisible: jest.fn().mockReturnThis(),
        on: jest.fn((eventName: string, handler: () => void) => {
          handlers[eventName] = handler;
          return object;
        }),
        destroy: jest.fn(),
      };
      return object;
    };
    add = {
      rectangle: jest.fn(() => this.createGameObject()),
      ellipse: jest.fn(() => this.createGameObject()),
      circle: jest.fn(() => this.createGameObject()),
      line: jest.fn(() => this.createGameObject()),
      triangle: jest.fn(() => this.createGameObject()),
      text: jest.fn(() => this.createGameObject()),
      image: jest.fn(() => this.createGameObject()),
      tileSprite: jest.fn(() => this.createGameObject()),
    };
    cameras = {
      main: {
        setBackgroundColor: jest.fn(),
        setZoom: jest.fn(),
        pan: jest.fn(),
      },
    };
    tweens = {
      add: jest.fn(),
    };
    textures = {
      exists: jest.fn(() => true),
    };
    make = {
      graphics: jest.fn(() => ({
        fillStyle: jest.fn().mockReturnThis(),
        fillRect: jest.fn().mockReturnThis(),
        generateTexture: jest.fn().mockReturnThis(),
        destroy: jest.fn(),
      })),
    };
    events = {
      emit: jest.fn(),
    };
    sys = {
      config: { key: "WorldScene" },
    };
  },
  Math: {
    RadToDeg: jest.fn((radians) => radians * (180 / globalThis.Math.PI)),
    DegToRad: jest.fn((degrees) => degrees * (globalThis.Math.PI / 180)),
    Angle: {
      Between: jest.fn(() => 0),
    },
  },
}));

describe("WorldScene", () => {
  const sceneWorld: SceneWorld = {
    runId: "run-1",
    locations: [
      {
        id: "loc-1",
        name: "Cafe",
        locationType: "cafe",
        visual: {
          visualPreset: "shop",
          glyph: "C",
        },
        x: 100,
        y: 120,
        capacity: 6,
        occupantCount: 1,
        heat: 0.5,
      },
    ],
    agents: [
      {
        id: "agent-1",
        name: "Mei",
        locationId: "loc-1",
        status: "talking",
        slotIndex: 0,
      },
    ],
    moveTrails: [
      {
        id: "move-1",
        actorName: "Mei",
        actorId: "agent-1",
        fromLocationId: "loc-1",
        toLocationId: "loc-1",
        recencyIndex: 0,
      },
    ],
    bubbles: [
      {
        id: "bubble-1",
        text: "你好",
        speakerAgentId: "agent-1",
        speakerName: "Mei",
        locationId: "loc-1",
        recencyIndex: 0,
      },
    ],
    ambience: {
      label: "夜晚",
      overlayColor: "rgba(15, 23, 42, 0.35)",
      isDark: true,
    },
    stage: {
      theme: "campus_night",
      groundPreset: "boardwalk",
    },
  };

  it("creates the scene shell", () => {
    const scene = new WorldScene();
    scene.create();
    expect(scene).toBeDefined();
  });

  it("syncs location and agent nodes", () => {
    const scene = new WorldScene();
    scene.create();
    scene.syncWorld(sceneWorld);
    expect(scene).toBeDefined();
  });

  it("creates scene nodes and emits click events from bound handlers", () => {
    const scene = new WorldScene();
    scene.create();
    scene.syncWorld(sceneWorld);

    expect(scene.add.image).toHaveBeenCalledTimes(2);
    expect(scene.add.line).toHaveBeenCalledTimes(1);
    expect(scene.add.triangle).toHaveBeenCalledTimes(1);

    const locationBody = (scene.add.image as jest.Mock).mock.results[0].value;
    const agentBody = (scene.add.image as jest.Mock).mock.results[1].value;
    locationBody.__handlers.pointerdown();
    agentBody.__handlers.pointerdown();

    expect(scene.events.emit).toHaveBeenCalledWith("location:click", "loc-1");
    expect(scene.events.emit).toHaveBeenCalledWith("agent:click", "agent-1");
    expect(scene.tweens.add).toHaveBeenCalled();
  });

  it("destroys stale scene nodes when world data removes them", () => {
    const scene = new WorldScene();
    scene.create();
    scene.syncWorld(sceneWorld);

    const locationBody = (scene.add.image as jest.Mock).mock.results[0].value;
    const agentBody = (scene.add.image as jest.Mock).mock.results[1].value;
    const trailLine = (scene.add.line as jest.Mock).mock.results[0].value;
    const bubbleBox = (scene.add.rectangle as jest.Mock).mock.results.at(-1)?.value;

    scene.syncWorld({
      ...sceneWorld,
      locations: [],
      agents: [],
      moveTrails: [],
      bubbles: [],
    });

    expect(locationBody.destroy).toHaveBeenCalled();
    expect(agentBody.destroy).toHaveBeenCalled();
    expect(trailLine.destroy).toHaveBeenCalled();
    expect(bubbleBox.destroy).toHaveBeenCalled();
  });
});
