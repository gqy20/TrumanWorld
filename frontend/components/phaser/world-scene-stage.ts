import type * as Phaser from "phaser";

import type { SceneWorld } from "@/lib/world-scene-adapter";
import type { TooltipNode } from "./world-scene-interactions";
import {
  CANVAS_HEIGHT,
  CANVAS_WIDTH,
  getStagePalette,
  mergeStagePalette,
  parseRgbaColor,
} from "./world-scene-style";

export type StageNodes = {
  stageGround: Phaser.GameObjects.TileSprite;
  stageHeader: Phaser.GameObjects.Rectangle;
  stageVignette: Phaser.GameObjects.Ellipse;
  ambienceOverlay: Phaser.GameObjects.Rectangle;
  ambienceLabel: Phaser.GameObjects.Text;
  tooltip: TooltipNode;
};

export function createStageShell(scene: Phaser.Scene): StageNodes {
  const palette = getStagePalette();
  scene.cameras.main.setBackgroundColor(palette.backgroundColor);
  scene.cameras.main.setZoom(1);

  const stageGround = scene.add
    .tileSprite(CANVAS_WIDTH / 2, CANVAS_HEIGHT / 2, CANVAS_WIDTH, CANVAS_HEIGHT, "pixel-ground")
    .setDepth(-20)
    .setAlpha(0.98);

  const stageHeader = scene.add
    .rectangle(CANVAS_WIDTH / 2, 86, CANVAS_WIDTH, 132, 0x172554)
    .setDepth(-19)
    .setAlpha(0.42);

  const stageVignette = scene.add
    .ellipse(CANVAS_WIDTH / 2, CANVAS_HEIGHT / 2 + 18, 700, 470, 0x0f172a)
    .setDepth(-18)
    .setAlpha(0.16);

  const ambienceOverlay = scene.add
    .rectangle(CANVAS_WIDTH / 2, CANVAS_HEIGHT / 2, CANVAS_WIDTH, CANVAS_HEIGHT, 0xffffff)
    .setDepth(-18)
    .setAlpha(0);

  const ambienceLabel = scene.add
    .text(20, 20, "World Stage", {
      color: palette.labelColor,
      fontFamily: "ui-monospace, SFMono-Regular, monospace",
      fontSize: "12px",
      fontStyle: "600",
    })
    .setDepth(60);

  const tooltipBox = scene.add
    .rectangle(0, 0, 160, 32, 0x020617, 0.92)
    .setStrokeStyle(1, 0x334155, 0.9)
    .setDepth(90)
    .setVisible(false);
  const tooltipText = scene.add
    .text(0, 0, "", {
      color: "#e2e8f0",
      fontFamily: "ui-monospace, SFMono-Regular, monospace",
      fontSize: "11px",
    })
    .setOrigin(0.5)
    .setDepth(91)
    .setVisible(false);

  return {
    stageGround,
    stageHeader,
    stageVignette,
    ambienceOverlay,
    ambienceLabel,
    tooltip: { box: tooltipBox, text: tooltipText },
  };
}

export function syncAmbience(nodes: StageNodes, world: SceneWorld): void {
  nodes.ambienceOverlay.setFillStyle(
    parseRgbaColor(world.ambience.overlayColor),
    world.ambience.isDark ? 0.24 : 0.1
  );
  nodes.ambienceLabel.setText(`Stage / ${world.ambience.label}`);
}

export function syncStageTheme(
  scene: Phaser.Scene,
  nodes: StageNodes,
  world: SceneWorld,
  ensureGroundTexture: (groundPreset: string) => string
): void {
  const palette = mergeStagePalette(getStagePalette(world.stage.theme), world.stage.palette);
  const groundPreset = world.stage.groundPreset ?? "default";
  const textureKey = ensureGroundTexture(groundPreset);
  scene.cameras.main.setBackgroundColor(palette.backgroundColor);
  nodes.stageGround.setTexture(textureKey);
  nodes.stageHeader.setFillStyle(palette.headerColor, palette.headerAlpha);
  nodes.stageVignette.setFillStyle(palette.vignetteColor, palette.vignetteAlpha);
  nodes.ambienceLabel.setColor(palette.labelColor);
}
