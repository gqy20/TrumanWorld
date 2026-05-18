import type * as Phaser from "phaser";

import type { SceneLocation, SceneWorld } from "@/lib/world-scene-adapter";
import type { TooltipNode } from "./world-scene-interactions";
import { isoTileToCanvas } from "./town-layout";
import {
  TOWN_SPRITESHEET_KEY,
  getTownPropAssetSpec,
  getTownTileAssetSpec,
  type TownAssetFrameSpec,
  type TownAssetPackManifest,
} from "./world-asset-pack";
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
  townAssetNodes: Phaser.GameObjects.Image[];
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
    .setAlpha(0.52);

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
    townAssetNodes: [],
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

export function syncTownGround(
  scene: Phaser.Scene,
  nodes: StageNodes,
  _locations: SceneLocation[],
  manifest?: TownAssetPackManifest | null,
): void {
  nodes.townTiles.clear();
  nodes.townRoads.clear();
  clearTownAssetNodes(nodes);

  for (let row = 0; row < ISO_GRID_ROWS; row += 1) {
    for (let column = 0; column < ISO_GRID_COLUMNS; column += 1) {
      const point = isoTileToCanvas(column, row);
      const color = (column + row) % 2 === 0 ? 0xb7d68c : 0x9cc774;
      drawIsoDiamond(nodes.townTiles, point.x, point.y, ISO_TILE_WIDTH, ISO_TILE_HEIGHT, color, 0.74);
    }
  }

  drawTownBlocks(nodes.townTiles);
  addRoadSprites(scene, nodes, manifest);
  addTownProps(scene, nodes, manifest);
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

function addRoadSprites(
  scene: Phaser.Scene,
  nodes: StageNodes,
  manifest?: TownAssetPackManifest | null,
): void {
  const roads = [
    ...range(0, 6).map((tileX) => ({ tileX, tileY: 3 })),
    ...range(0, 6).map((tileY) => ({ tileX: 3, tileY })),
    ...range(1, 5).map((tileX) => ({ tileX, tileY: 5 })),
    { tileX: 1, tileY: 4 },
    { tileX: 5, tileY: 4 },
  ];
  const roadTiles = new Map<string, { tileX: number; tileY: number }>();

  for (const road of roads) {
    const key = `${road.tileX}:${road.tileY}`;
    roadTiles.set(key, road);
  }

  for (const road of roadTiles.values()) {
    const point = isoTileToCanvas(road.tileX, road.tileY);
    const roadShape = resolveRoadShape(road, roadTiles);
    addTownAsset(
      scene,
      nodes,
      getTownTileAssetSpec(roadShape.assetKey, manifest),
      point.x,
      point.y,
      -14,
      0.96,
    );
  }
}

function resolveRoadShape(
  road: { tileX: number; tileY: number },
  roadTiles: Map<string, { tileX: number; tileY: number }>,
) {
  const directions = [
    { key: "northWest", dx: -1, dy: 0, rotation: 0 },
    { key: "northEast", dx: 0, dy: -1, rotation: 90 },
    { key: "southEast", dx: 1, dy: 0, rotation: 180 },
    { key: "southWest", dx: 0, dy: 1, rotation: 270 },
  ];
  const connected = directions.filter((direction) =>
    roadTiles.has(`${road.tileX + direction.dx}:${road.tileY + direction.dy}`)
  );

  if (connected.length >= 4) {
    return { assetKey: "roadCross" };
  }
  if (connected.length === 3) {
    return { assetKey: "roadT" };
  }
  if (connected.length === 2) {
    const [first, second] = connected;
    const isStraight =
      (first.key === "northWest" && second.key === "southEast") ||
      (first.key === "northEast" && second.key === "southWest");
    if (isStraight) {
      return { assetKey: "roadStraight" };
    }
    return { assetKey: "roadBend" };
  }
  if (connected.length === 1) {
    return { assetKey: "roadEnd" };
  }
  return { assetKey: "roadDot" };
}

function addTownProps(
  scene: Phaser.Scene,
  nodes: StageNodes,
  manifest?: TownAssetPackManifest | null,
): void {
  const props = [
    { key: "tree", tileX: 0.55, tileY: 1.75 },
    { key: "tree", tileX: 1.35, tileY: 0.9 },
    { key: "tree", tileX: 0.55, tileY: 4.65 },
    { key: "shrub", tileX: 5.95, tileY: 1.55 },
    { key: "shrub", tileX: 1.45, tileY: 6.05 },
    { key: "lamp", tileX: 2.12, tileY: 3.04 },
    { key: "lamp", tileX: 4.82, tileY: 3.04 },
    { key: "lamp", tileX: 3.08, tileY: 4.36 },
    { key: "bench", tileX: 2.08, tileY: 5.08 },
    { key: "bench", tileX: 4.66, tileY: 5.08 },
    { key: "flowers", tileX: 5.64, tileY: 4.72 },
    { key: "flowers", tileX: 1.26, tileY: 2.82 },
  ];

  for (const prop of props) {
    const point = isoTileToCanvas(prop.tileX, prop.tileY);
    addTownAsset(
      scene,
      nodes,
      getTownPropAssetSpec(prop.key, manifest),
      point.x,
      point.y,
      Math.round(point.y) + 2,
      1,
    );
  }
}

function addTownAsset(
  scene: Phaser.Scene,
  nodes: StageNodes,
  spec: TownAssetFrameSpec,
  x: number,
  y: number,
  depth: number,
  alpha: number,
): void {
  const [originX, originY] = spec.anchor ?? [0.5, 0.5];
  const display = spec.display ?? [ISO_TILE_WIDTH, ISO_TILE_HEIGHT];
  const scale = depth < 0 ? ISO_TILE_WIDTH / 78 : 1;
  const [width, height] = [display[0] * scale, display[1] * scale];
  const image = scene.add
    .image(x, y, TOWN_SPRITESHEET_KEY, spec.frame)
    .setOrigin(originX, originY)
    .setDisplaySize(width, height)
    .setDepth(depth)
    .setAlpha(alpha);
  nodes.townAssetNodes.push(image);
}

function clearTownAssetNodes(nodes: StageNodes): void {
  for (const node of nodes.townAssetNodes) {
    node.destroy();
  }
  nodes.townAssetNodes = [];
}

function range(from: number, to: number): number[] {
  return Array.from({ length: to - from + 1 }, (_, index) => from + index);
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
  graphics.lineStyle(1, 0xf8fafc, 0.08);
  graphics.strokePath();
}
