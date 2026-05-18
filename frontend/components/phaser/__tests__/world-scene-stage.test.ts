import type { SceneWorld } from "@/lib/world-scene-adapter";

import { createStageShell, syncAmbience, syncStageTheme, type StageNodes } from "../world-scene-stage";

function gameObject(overrides: Record<string, unknown> = {}) {
  return {
    setAlpha: jest.fn().mockReturnThis(),
    beginPath: jest.fn().mockReturnThis(),
    clear: jest.fn().mockReturnThis(),
    closePath: jest.fn().mockReturnThis(),
    fillPath: jest.fn().mockReturnThis(),
    setColor: jest.fn().mockReturnThis(),
    setDepth: jest.fn().mockReturnThis(),
    setFillStyle: jest.fn().mockReturnThis(),
    setOrigin: jest.fn().mockReturnThis(),
    setStrokeStyle: jest.fn().mockReturnThis(),
    setText: jest.fn().mockReturnThis(),
    setTexture: jest.fn().mockReturnThis(),
    setVisible: jest.fn().mockReturnThis(),
    fillStyle: jest.fn().mockReturnThis(),
    lineStyle: jest.fn().mockReturnThis(),
    lineTo: jest.fn().mockReturnThis(),
    moveTo: jest.fn().mockReturnThis(),
    strokePath: jest.fn().mockReturnThis(),
    ...overrides,
  };
}

function stageNodes(): StageNodes {
  return {
    stageGround: gameObject(),
    townTiles: gameObject(),
    townRoads: gameObject(),
    stageHeader: gameObject(),
    stageVignette: gameObject(),
    ambienceOverlay: gameObject(),
    ambienceLabel: gameObject(),
    tooltip: {
      box: gameObject(),
      text: gameObject(),
    },
  } as unknown as StageNodes;
}

function sceneWorld(overrides: Partial<SceneWorld> = {}): SceneWorld {
  return {
    runId: "run-1",
    locations: [],
    agents: [],
    moveTrails: [],
    bubbles: [],
    ambience: {
      label: "夜晚",
      overlayColor: "rgba(15, 23, 42, 0.35)",
      isDark: true,
    },
    stage: {
      theme: "campus_night",
      groundPreset: "boardwalk",
      palette: {
        headerColor: "rgb(14, 165, 233)",
      },
    },
    ...overrides,
  };
}

describe("world scene stage helpers", () => {
  it("creates the stage shell and tooltip nodes", () => {
    const scene = {
      cameras: {
        main: {
          setBackgroundColor: jest.fn(),
          setZoom: jest.fn(),
        },
      },
      add: {
        tileSprite: jest.fn(() => gameObject()),
        graphics: jest.fn(() => gameObject()),
        rectangle: jest.fn(() => gameObject()),
        ellipse: jest.fn(() => gameObject()),
        text: jest.fn(() => gameObject()),
      },
    };

    const nodes = createStageShell(scene as never);

    expect(scene.cameras.main.setBackgroundColor).toHaveBeenCalled();
    expect(scene.cameras.main.setZoom).toHaveBeenCalledWith(1);
    expect(scene.add.tileSprite).toHaveBeenCalledTimes(1);
    expect(scene.add.graphics).toHaveBeenCalledTimes(2);
    expect(scene.add.rectangle).toHaveBeenCalledTimes(3);
    expect(scene.add.ellipse).toHaveBeenCalledTimes(1);
    expect(scene.add.text).toHaveBeenCalledTimes(2);
    expect(nodes.tooltip.box).toBeDefined();
    expect(nodes.tooltip.text).toBeDefined();
  });

  it("syncs ambience overlay and label", () => {
    const nodes = stageNodes();

    syncAmbience(nodes, sceneWorld());

    expect(nodes.ambienceOverlay.setFillStyle).toHaveBeenCalledWith(0x0f172a, 0.24);
    expect(nodes.ambienceLabel.setText).toHaveBeenCalledWith("Stage / 夜晚");
  });

  it("syncs stage theme, ground texture, and configured palette", () => {
    const scene = {
      cameras: {
        main: {
          setBackgroundColor: jest.fn(),
        },
      },
    };
    const nodes = stageNodes();
    const ensureGroundTexture = jest.fn(() => "pixel-ground-boardwalk");

    syncStageTheme(scene as never, nodes, sceneWorld(), ensureGroundTexture);

    expect(ensureGroundTexture).toHaveBeenCalledWith("boardwalk");
    expect(scene.cameras.main.setBackgroundColor).toHaveBeenCalled();
    expect(nodes.stageGround.setTexture).toHaveBeenCalledWith("pixel-ground-boardwalk");
    expect(nodes.stageHeader.setFillStyle).toHaveBeenCalledWith(0x0ea5e9, expect.any(Number));
    expect(nodes.stageVignette.setFillStyle).toHaveBeenCalled();
    expect(nodes.ambienceLabel.setColor).toHaveBeenCalled();
  });
});
