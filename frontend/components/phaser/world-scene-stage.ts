import type * as Phaser from "phaser";

import type { SceneLocation, SceneWorld } from "@/lib/world-scene-adapter";
import { mapWorldToCanvas } from "./world-scene-geometry";
import type { TooltipNode } from "./world-scene-interactions";
import { isoTileToCanvas } from "./town-layout";
import {
  CANVAS_HEIGHT,
  CANVAS_WIDTH,
  ISO_GRID_COLUMNS,
  ISO_GRID_ROWS,
  ISO_TILE_HEIGHT,
  ISO_TILE_WIDTH,
  getStagePalette,
  mergeStagePalette,
  parseRgbaColor,
} from "./world-scene-style";

export type StageNodes = {
  stageGround: Phaser.GameObjects.TileSprite;
  townTiles: Phaser.GameObjects.Graphics;
  townRoads: Phaser.GameObjects.Graphics;
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

  const townTiles = scene.add.graphics().setDepth(-16);
  const townRoads = scene.add.graphics().setDepth(-15);

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
    townTiles,
    townRoads,
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

export function syncTownGround(nodes: StageNodes, locations: SceneLocation[]): void {
  nodes.townTiles.clear();
  nodes.townRoads.clear();

  for (let row = 0; row < ISO_GRID_ROWS; row += 1) {
    for (let column = 0; column < ISO_GRID_COLUMNS; column += 1) {
      const point = isoTileToCanvas(column, row);
      const color = (column + row) % 2 === 0 ? 0xb7d68c : 0x9cc774;
      drawIsoDiamond(nodes.townTiles, point.x, point.y, ISO_TILE_WIDTH, ISO_TILE_HEIGHT, color, 0.64);
    }
  }

  drawTownBlocks(nodes.townTiles);
  drawMainRoads(nodes.townRoads);
  drawLocationRoads(nodes.townRoads, locations);
}

function drawTownBlocks(graphics: Phaser.GameObjects.Graphics): void {
  const blocks = [
    { tileX: 1, tileY: 4, color: 0xb3c6d8, alpha: 0.22 },
    { tileX: 3, tileY: 5, color: 0xf3d28f, alpha: 0.24 },
    { tileX: 5, tileY: 2, color: 0xa8c3e8, alpha: 0.2 },
    { tileX: 1, tileY: 2, color: 0x86c779, alpha: 0.24 },
  ];

  for (const block of blocks) {
    const point = isoTileToCanvas(block.tileX, block.tileY);
    drawIsoDiamond(
      graphics,
      point.x,
      point.y,
      ISO_TILE_WIDTH * 1.72,
      ISO_TILE_HEIGHT * 1.72,
      block.color,
      block.alpha,
    );
  }
}

function drawMainRoads(graphics: Phaser.GameObjects.Graphics): void {
  graphics.lineStyle(12, 0xe7d4aa, 0.78);
  drawIsoPath(graphics, isoTileToCanvas(0, 3), isoTileToCanvas(6, 3));
  drawIsoPath(graphics, isoTileToCanvas(3, 0), isoTileToCanvas(3, 6));
  drawIsoPath(graphics, isoTileToCanvas(1, 5), isoTileToCanvas(5, 5));
  graphics.lineStyle(3, 0xf8efd7, 0.8);
  drawIsoPath(graphics, isoTileToCanvas(0, 3), isoTileToCanvas(6, 3));
  drawIsoPath(graphics, isoTileToCanvas(3, 0), isoTileToCanvas(3, 6));
  drawIsoPath(graphics, isoTileToCanvas(1, 5), isoTileToCanvas(5, 5));
}

function drawLocationRoads(graphics: Phaser.GameObjects.Graphics, locations: SceneLocation[]): void {
  const townCenter = isoTileToCanvas(3, 3);
  graphics.lineStyle(5, 0xd9bd84, 0.54);

  for (const location of locations) {
    const locationPoint = mapWorldToCanvas(location.x, location.y, locations);
    const threshold = Math.abs(locationPoint.x - townCenter.x) + Math.abs(locationPoint.y - townCenter.y);
    if (threshold > 26) {
      drawIsoPath(graphics, townCenter, locationPoint);
    }
  }
}

function drawIsoDiamond(
  graphics: Phaser.GameObjects.Graphics,
  x: number,
  y: number,
  width: number,
  height: number,
  color: number,
  alpha: number,
): void {
  graphics.fillStyle(color, alpha);
  graphics.beginPath();
  graphics.moveTo(x, y - height / 2);
  graphics.lineTo(x + width / 2, y);
  graphics.lineTo(x, y + height / 2);
  graphics.lineTo(x - width / 2, y);
  graphics.closePath();
  graphics.fillPath();
  graphics.lineStyle(1, 0xf8fafc, 0.18);
  graphics.strokePath();
}

function drawIsoPath(
  graphics: Phaser.GameObjects.Graphics,
  from: { x: number; y: number },
  to: { x: number; y: number },
): void {
  graphics.beginPath();
  graphics.moveTo(from.x, from.y);
  graphics.lineTo(to.x, to.y);
  graphics.strokePath();
}
