import type { SceneWorld } from "@/lib/world-scene-adapter";

import { VOXEL_SCENE_SCALE } from "./scene-scale";
import type { VoxelBlockWriter, VoxelPoint } from "./types";

export type AmbientFrame = {
  centerX: number;
  centerZ: number;
  depth: number;
  width: number;
};

type AmbientLot = VoxelPoint & { rotationY: number };
type AmbientVariant = "campus" | "seaside" | "town";

export function buildAmbientWorld(
  addBlock: VoxelBlockWriter,
  frame: AmbientFrame,
  stage: SceneWorld["stage"],
): void {
  const stageIdentity = `${stage.theme ?? ""} ${stage.groundPreset ?? ""}`.toLowerCase();
  const isSeaside = stageIdentity.includes("sea") || stage.groundPreset === "boardwalk";
  const isCampus = stageIdentity.includes("campus");
  const outerWidth = frame.width * 1.58;
  const outerDepth = frame.depth * 1.58;

  addBlock(
    "ambient-ground",
    [frame.centerX, -0.1, frame.centerZ],
    [outerWidth, 0.18, outerDepth],
    "groundBase",
    { castShadow: false, layer: "ambient" },
  );
  addAmbientRoadExits(addBlock, frame);

  buildAmbientLots(frame, isSeaside).forEach((lot, index) => {
    buildAmbientBuilding(addBlock, lot, index, isCampus);
  });
  buildAmbientTreeBelt(
    addBlock,
    frame,
    isSeaside ? "seaside" : isCampus ? "campus" : "town",
  );

  if (isSeaside) buildSeasideEdge(addBlock, frame);
  else if (isCampus) buildCampusEdge(addBlock, frame);
}

function buildAmbientLots(frame: AmbientFrame, omitSouth: boolean): AmbientLot[] {
  const xOffsets = [-0.34, 0, 0.34] as const;
  const zOffsets = [-0.32, 0.04, 0.36] as const;
  const lots: AmbientLot[] = [
    ...zOffsets.map((offset) => ({
      x: frame.centerX - frame.width * 0.66,
      z: frame.centerZ + frame.depth * offset,
      rotationY: Math.PI / 2,
    })),
    ...zOffsets.map((offset) => ({
      x: frame.centerX + frame.width * 0.66,
      z: frame.centerZ + frame.depth * offset,
      rotationY: -Math.PI / 2,
    })),
    ...xOffsets.map((offset) => ({
      x: frame.centerX + frame.width * offset,
      z: frame.centerZ - frame.depth * 0.66,
      rotationY: 0,
    })),
  ];
  if (!omitSouth) {
    lots.push(
      ...xOffsets.map((offset) => ({
        x: frame.centerX + frame.width * offset,
        z: frame.centerZ + frame.depth * 0.66,
        rotationY: Math.PI,
      })),
    );
  }
  return lots;
}

function buildAmbientBuilding(
  addBlock: VoxelBlockWriter,
  lot: AmbientLot,
  index: number,
  isCampus: boolean,
): void {
  const width = isCampus ? 1.55 + (index % 2) * 0.22 : 1.02 + (index % 3) * 0.16;
  const depth = isCampus ? 1.18 : 0.88 + (index % 2) * 0.12;
  const height = isCampus ? 1.18 + (index % 3) * 0.16 : 0.86 + (index % 4) * 0.14;
  const wall = index % 3 === 0 ? "wallCool" : index % 3 === 1 ? "wallWarm" : "wallStone";
  const roof = index % 2 === 0 ? "roofRed" : "roofBlue";
  const layer = "ambient" as const;

  addBlock(
    "ambient-lot",
    [lot.x, 0.015, lot.z],
    [width + 0.5, 0.03, depth + 0.52],
    "grassAlt",
    {
      castShadow: false,
      geometry: "cylinder",
      layer,
      rotationY: lot.rotationY,
    },
  );
  addBlock(
    "ambient-building-shadow",
    [lot.x, 0.04, lot.z],
    [width + 0.08, 0.08, depth + 0.08],
    "shadow",
    { castShadow: false, layer, rotationY: lot.rotationY },
  );
  addBlock(
    "ambient-building",
    [lot.x, height / 2 + 0.08, lot.z],
    [width, height, depth],
    wall,
    { layer, rotationY: lot.rotationY },
  );
  addBlock(
    "ambient-roof",
    [lot.x, height + 0.34, lot.z],
    [width + 0.22, 0.62, depth + 0.22],
    roof,
    { geometry: "cone", layer, rotationY: lot.rotationY + Math.PI / 4 },
  );

  for (const side of [-1, 1] as const) {
    const forwardX = Math.sin(lot.rotationY) * (depth / 2 + 0.012);
    const forwardZ = Math.cos(lot.rotationY) * (depth / 2 + 0.012);
    const rightX = Math.cos(lot.rotationY) * side * width * 0.26;
    const rightZ = -Math.sin(lot.rotationY) * side * width * 0.26;
    addBlock(
      "ambient-window",
      [lot.x + forwardX + rightX, height * 0.55 + 0.08, lot.z + forwardZ + rightZ],
      [0.2, 0.22, 0.04],
      "glass",
      { castShadow: false, layer, rotationY: lot.rotationY },
    );
  }
}

function addAmbientRoadExits(addBlock: VoxelBlockWriter, frame: AmbientFrame): void {
  const layer = "ambient" as const;
  for (const direction of [-1, 1] as const) {
    addBlock(
      "ambient-road-exit",
      [frame.centerX + direction * frame.width * 0.61, 0.012, frame.centerZ],
      [frame.width * 0.26, 0.024, VOXEL_SCENE_SCALE.roadSurfaceWidth],
      "road",
      { castShadow: false, layer },
    );
    addBlock(
      "ambient-road-exit",
      [frame.centerX, 0.012, frame.centerZ + direction * frame.depth * 0.61],
      [VOXEL_SCENE_SCALE.roadSurfaceWidth, 0.024, frame.depth * 0.26],
      "road",
      { castShadow: false, layer },
    );
  }
}

function buildAmbientTreeBelt(
  addBlock: VoxelBlockWriter,
  frame: AmbientFrame,
  variant: AmbientVariant,
): void {
  const layer = "ambient" as const;
  const positions = [
    [-0.58, -0.53],
    [-0.42, -0.58],
    [-0.12, -0.58],
    [0.18, -0.58],
    [0.48, -0.54],
    [-0.59, -0.18],
    [-0.61, 0.23],
    [0.6, -0.24],
    [0.61, 0.2],
    [-0.48, 0.56],
    [-0.18, 0.59],
    [0.18, 0.59],
    [0.48, 0.55],
  ] as const;
  positions.forEach(([offsetX, offsetZ], index) => {
    if (variant === "seaside" && offsetZ > 0.5) return;
    const x = frame.centerX + frame.width * offsetX;
    const z = frame.centerZ + frame.depth * offsetZ;
    const scale = 0.68 + (index % 4) * 0.1;
    addBlock(
      "ambient-tree",
      [x, 0.32 * scale, z],
      [0.13, 0.64 * scale, 0.13],
      "trunk",
      { geometry: "cylinder", layer },
    );
    addBlock(
      "ambient-tree",
      [x, 0.84 * scale, z],
      [0.62 * scale, 0.72 * scale, 0.62 * scale],
      index % 2 ? "leaf" : "leafLight",
      { geometry: "icosphere", layer },
    );
  });
}

function buildSeasideEdge(addBlock: VoxelBlockWriter, frame: AmbientFrame): void {
  const layer = "ambient" as const;
  const waterZ = frame.centerZ + frame.depth * 0.83;
  addBlock(
    "ambient-sea",
    [frame.centerX, -0.04, waterZ],
    [frame.width * 1.55, 0.08, frame.depth * 0.5],
    "water",
    { castShadow: false, layer },
  );
  addBlock(
    "ambient-seawall",
    [frame.centerX, 0.08, frame.centerZ + frame.depth * 0.59],
    [frame.width * 1.18, 0.18, 0.18],
    "wallStone",
    { layer },
  );
  for (const offsetX of [-0.28, 0.22] as const) {
    const x = frame.centerX + frame.width * offsetX;
    addBlock(
      "ambient-pier",
      [x, 0.08, frame.centerZ + frame.depth * 0.72],
      [0.62, 0.12, frame.depth * 0.42],
      "wood",
      { layer },
    );
  }
}

function buildCampusEdge(addBlock: VoxelBlockWriter, frame: AmbientFrame): void {
  const layer = "ambient" as const;
  for (const offsetX of [-0.18, 0.18] as const) {
    const x = frame.centerX + frame.width * offsetX;
    addBlock(
      "ambient-campus-walk",
      [x, 0.014, frame.centerZ],
      [0.3, 0.028, frame.depth * 1.28],
      "paving",
      { castShadow: false, layer },
    );
  }
}
