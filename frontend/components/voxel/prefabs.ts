import type { SceneLocation } from "@/lib/world-scene-adapter";

import type {
  VoxelMaterialKey,
  VoxelPlot,
  VoxelPrefab,
  VoxelPrefabBlock,
  VoxelVector3,
} from "./types";
import { VOXEL_SCENE_SCALE } from "./scene-scale";

type PrefabWriter = (
  position: [number, number, number],
  size: [number, number, number],
  material: VoxelMaterialKey,
  options?: Pick<
    VoxelPrefabBlock,
    "castShadow" | "geometry" | "receiveShadow" | "rotationY"
  >,
) => void;

export function buildLocationPrefab(location: SceneLocation, plotItem: VoxelPlot): VoxelPrefab {
  const type = (location.visual.visualPreset ?? location.locationType).toLowerCase();
  const kind = resolvePrefabKind(type, location.locationType);
  const blocks: VoxelPrefabBlock[] = [];
  const add: PrefabWriter = (position, size, material, options = {}) => {
    blocks.push({
      position: toVector3(position),
      size: toVector3(size),
      material,
      geometry: options.geometry,
      rotationY: options.rotationY,
      castShadow: options.castShadow,
      receiveShadow: options.receiveShadow,
    });
  };

  switch (kind) {
    case "green":
      buildGreenPrefab(add, plotItem);
      break;
    case "plaza":
      buildPlazaPrefab(add, plotItem);
      break;
    case "home":
      buildHomePrefab(add, plotItem);
      break;
    case "cafe":
      buildCafePrefab(add, plotItem);
      break;
    case "office":
      buildOfficePrefab(add, plotItem);
      break;
    case "library":
      buildLibraryPrefab(add, plotItem);
      break;
    case "hospital":
      buildHospitalPrefab(add, plotItem);
      break;
    default:
      buildGenericPrefab(add, plotItem);
  }

  return {
    kind,
    blocks: orientBlocks(blocks, resolveEntranceRotation(plotItem)),
  };
}

export function resolvePrefabKind(
  visualPreset: string,
  locationType: string,
): VoxelPrefab["kind"] {
  const type = `${visualPreset} ${locationType}`.toLowerCase();
  if (includesAny(type, ["park", "grove", "quad", "garden"])) return "green";
  if (includesAny(type, ["plaza", "square", "center"])) return "plaza";
  if (includesAny(type, ["cafe", "shop", "mall", "store"])) return "cafe";
  if (includesAny(type, ["office", "tower"])) return "office";
  if (includesAny(type, ["library", "hall", "school"])) return "library";
  if (includesAny(type, ["hospital", "clinic"])) return "hospital";
  if (includesAny(type, ["home", "house", "dorm", "apartment"])) return "home";
  return "generic";
}

function buildHomePrefab(add: PrefabWriter, plotItem: VoxelPlot): void {
  const height = 1.12;
  addBuildingBase(add, plotItem, height, "wallWarm");
  addHippedRoof(add, plotItem, height, "roofRed");
  addFrontDoorAndWindows(add, plotItem, height);
  add([0.42, height + 0.34, 0.16], [0.15, 0.5, 0.15], "wood");
  add([-0.48, 0.22, plotItem.footprint.depth / 2 + 0.2], [0.48, 0.12, 0.18], "wood");
}

function buildCafePrefab(add: PrefabWriter, plotItem: VoxelPlot): void {
  const height = 1.08;
  const front = plotItem.footprint.depth / 2;
  addBuildingBase(add, plotItem, height, "wallWarm");
  addHippedRoof(add, plotItem, height, "roofRed");
  addFrontDoorAndWindows(add, plotItem, height);
  add([0, 0.88, front + 0.16], [1.28, 0.14, 0.36], "white");
  for (const x of [-0.42, -0.14, 0.14, 0.42]) {
    add([x, 0.89, front + 0.34], [0.16, 0.15, 0.05], "roofRed");
  }
  add([0.48, 0.42, front + 0.12], [0.2, 0.22, 0.06], "flower");
  add([-0.5, 0.16, front + 0.46], [0.42, 0.1, 0.42], "wood", { geometry: "cylinder" });
  add([-0.5, 0.48, front + 0.46], [0.06, 0.56, 0.06], "wood", { geometry: "cylinder" });
}

function buildOfficePrefab(add: PrefabWriter, plotItem: VoxelPlot): void {
  const height = 1.8;
  const front = plotItem.footprint.depth / 2;
  addBuildingBase(add, plotItem, height, "wallCool");
  add([0, height + 0.12, 0], [plotItem.footprint.width + 0.08, 0.24, plotItem.footprint.depth + 0.08], "roofBlue");
  add([0, height + 0.3, 0], [0.76, 0.16, 0.76], "roofBlue");
  add([0, 0.43, front + 0.04], [0.34, VOXEL_SCENE_SCALE.doorHeight, 0.06], "wood");
  for (const y of [0.78, 1.16, 1.52]) {
    add([-0.34, y, front + 0.035], [0.26, 0.2, 0.05], "glass");
    add([0.34, y, front + 0.035], [0.26, 0.2, 0.05], "glass");
  }
}

function buildLibraryPrefab(add: PrefabWriter, plotItem: VoxelPlot): void {
  const height = 1.22;
  const front = plotItem.footprint.depth / 2;
  addBuildingBase(add, plotItem, height, "wallStone");
  addHippedRoof(add, plotItem, height, "roofBlue", 0.46);
  add([0, 0.12, front + 0.25], [plotItem.footprint.width * 0.88, 0.12, 0.42], "paving");
  for (const x of [-0.48, 0, 0.48]) {
    add([x, 0.58, front + 0.08], [0.12, 0.88, 0.12], "white");
  }
  add([0, 0.5, front + 0.1], [0.32, 0.62, 0.08], "wood");
}

function buildHospitalPrefab(add: PrefabWriter, plotItem: VoxelPlot): void {
  const height = 1.38;
  const front = plotItem.footprint.depth / 2;
  addBuildingBase(add, plotItem, height, "wallCool");
  add([0, height + 0.1, 0], [plotItem.footprint.width + 0.12, 0.2, plotItem.footprint.depth + 0.12], "white");
  add([0, height + 0.23, 0], [0.54, 0.06, 0.14], "roofRed");
  add([0, height + 0.23, 0], [0.14, 0.06, 0.54], "roofRed");
  add([0, 0.43, front + 0.04], [0.34, VOXEL_SCENE_SCALE.doorHeight, 0.06], "glass");
  add([0, 1.06, front + 0.08], [0.48, 0.12, 0.06], "roofRed");
  add([0, 1.06, front + 0.08], [0.12, 0.48, 0.06], "roofRed");
  for (const x of [-0.42, 0.42]) {
    add([x, 0.82, front + 0.04], [0.24, 0.2, 0.05], "glass");
  }
}

function buildGenericPrefab(add: PrefabWriter, plotItem: VoxelPlot): void {
  const height = 1.08;
  addBuildingBase(add, plotItem, height, "wallWarm");
  addHippedRoof(add, plotItem, height, "roofGreen");
  addFrontDoorAndWindows(add, plotItem, height);
}

function buildPlazaPrefab(add: PrefabWriter, plotItem: VoxelPlot): void {
  add(
    [0, 0.1, 0],
    [plotItem.size.width - 0.28, 0.14, plotItem.size.depth - 0.28],
    "paving",
    { castShadow: false },
  );
  add([0, 0.22, 0], [1.18, 0.22, 1.18], "wallStone", { geometry: "cylinder" });
  add([0, 0.35, 0], [0.9, 0.08, 0.9], "water", { castShadow: false, geometry: "cylinder" });
  add([0, 0.72, 0], [0.16, 0.74, 0.16], "white", { geometry: "cylinder" });
  add([0, 1.08, 0], [0.38, 0.14, 0.38], "wallStone", { geometry: "cylinder" });
  add([0, 1.18, 0], [0.24, 0.2, 0.24], "water", { geometry: "icosphere" });
  for (const [x, z] of [
    [-0.92, -0.92],
    [0.92, -0.92],
    [-0.92, 0.92],
    [0.92, 0.92],
  ] as const) {
    add([x, 0.28, z], [0.42, 0.14, 0.16], "wood");
  }
}

function buildGreenPrefab(add: PrefabWriter, plotItem: VoxelPlot): void {
  add(
    [0, 0.08, 0],
    [plotItem.size.width - 0.4, 0.12, plotItem.size.depth - 0.4],
    "grass",
    { castShadow: false },
  );
  buildTree(add, -0.42, -0.3, 1.12);
  buildTree(add, 0.46, 0.3, 0.76);
  add([0.08, 0.18, -0.56], [0.7, 0.08, 0.18], "road");
  add([0.08, 0.3, -0.56], [0.58, 0.14, 0.12], "wood");
  add([-0.18, 0.22, -0.56], [0.1, 0.34, 0.1], "wood");
  add([0.34, 0.22, -0.56], [0.1, 0.34, 0.1], "wood");
  add([-0.55, 0.18, 0.5], [0.16, 0.08, 0.16], "flower");
  add([0.58, 0.18, -0.2], [0.16, 0.08, 0.16], "flowerPink");
}

function addBuildingBase(
  add: PrefabWriter,
  plotItem: VoxelPlot,
  height: number,
  material: VoxelMaterialKey,
): void {
  add(
    [0, VOXEL_SCENE_SCALE.buildingPlinthHeight / 2, 0],
    [
      plotItem.footprint.width + 0.08,
      VOXEL_SCENE_SCALE.buildingPlinthHeight,
      plotItem.footprint.depth + 0.08,
    ],
    "shadow",
  );
  add([0, height / 2, 0], [plotItem.footprint.width, height, plotItem.footprint.depth], material);
}

function addHippedRoof(
  add: PrefabWriter,
  plotItem: VoxelPlot,
  height: number,
  material: VoxelMaterialKey,
  roofHeight = 0.58,
): void {
  add(
    [0, height + roofHeight / 2 - 0.02, 0],
    [plotItem.footprint.width + 0.22, roofHeight, plotItem.footprint.depth + 0.2],
    material,
    { geometry: "cone", rotationY: Math.PI / 4 },
  );
}

function addFrontDoorAndWindows(add: PrefabWriter, plotItem: VoxelPlot, height: number): void {
  const front = plotItem.footprint.depth / 2;
  add([0, 0.43, front + 0.035], [0.3, VOXEL_SCENE_SCALE.doorHeight, 0.06], "wood");
  add([-0.38, height * 0.62, front + 0.035], [0.24, 0.2, 0.05], "glass");
  add([0.38, height * 0.62, front + 0.035], [0.24, 0.2, 0.05], "glass");
}

function buildTree(add: PrefabWriter, x: number, z: number, scale: number): void {
  add([x, 0.35 * scale, z], [0.16 * scale, 0.7 * scale, 0.16 * scale], "trunk", { geometry: "cylinder" });
  add([x, 0.9 * scale, z], [0.78 * scale, 0.62 * scale, 0.78 * scale], "leaf", { geometry: "icosphere" });
  add(
    [x - 0.12 * scale, 1.18 * scale, z - 0.08 * scale],
    [0.5 * scale, 0.42 * scale, 0.5 * scale],
    "leafLight",
    { geometry: "icosphere" },
  );
}

function orientBlocks(blocks: VoxelPrefabBlock[], rotationY: number): VoxelPrefabBlock[] {
  const cos = Math.round(Math.cos(rotationY));
  const sin = Math.round(Math.sin(rotationY));
  return blocks.map((block) => ({
    ...block,
    position: {
      x: block.position.x * cos + block.position.z * sin,
      y: block.position.y,
      z: -block.position.x * sin + block.position.z * cos,
    },
    rotationY: (block.rotationY ?? 0) + rotationY,
  }));
}

function resolveEntranceRotation(plotItem: VoxelPlot): number {
  const deltaX = plotItem.entrance.x - plotItem.center.x;
  const deltaZ = plotItem.entrance.z - plotItem.center.z;
  if (Math.abs(deltaX) > Math.abs(deltaZ)) return deltaX > 0 ? Math.PI / 2 : -Math.PI / 2;
  return deltaZ >= 0 ? 0 : Math.PI;
}

function includesAny(value: string, candidates: string[]): boolean {
  return candidates.some((candidate) => value.includes(candidate));
}

function toVector3(value: [number, number, number]): VoxelVector3 {
  return { x: value[0], y: value[1], z: value[2] };
}
