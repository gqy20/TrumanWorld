import type { VoxelMaterialKey } from "./types";

export const VOXEL_BACKGROUND_COLOR = 0xeef5e8;

export type VoxelMaterialSpec = {
  color: number;
  roughness: number;
  metalness?: number;
  emissive?: number;
  emissiveIntensity?: number;
};

export type VoxelMaterialClass = "emissive" | "glass" | "matte" | "water";

/** The approved 3D V2 palette translated into restrained, matte PBR materials. */
export const VOXEL_MATERIAL_SPECS: Record<VoxelMaterialKey, VoxelMaterialSpec> = {
  agent: { color: 0xd86f45, roughness: 0.8 },
  agentMoving: { color: 0x526b7a, roughness: 0.82 },
  agentResting: { color: 0x7a7291, roughness: 0.85 },
  agentTalking: { color: 0xf2b45b, roughness: 0.76 },
  agentWorking: { color: 0x667c5b, roughness: 0.84 },
  curb: { color: 0x918d84, roughness: 0.96 },
  flower: { color: 0xf2b45b, roughness: 0.82 },
  flowerPink: { color: 0xc46f78, roughness: 0.82 },
  glass: { color: 0xd6b579, roughness: 0.3, metalness: 0.02, emissive: 0xf2b45b, emissiveIntensity: 0.12 },
  grass: { color: 0x7f9a68, roughness: 0.98 },
  grassAlt: { color: 0x91a979, roughness: 0.98 },
  groundBase: { color: 0x667c5b, roughness: 1 },
  hair: { color: 0x2d2a29, roughness: 0.92 },
  highlight: { color: 0xf2b45b, roughness: 0.74, emissive: 0xd86f45, emissiveIntensity: 0.08 },
  leaf: { color: 0x667c5b, roughness: 0.98 },
  leafLight: { color: 0x7f9a68, roughness: 0.98 },
  plot: { color: 0x8b9b76, roughness: 1 },
  paving: { color: 0xb9b4aa, roughness: 0.96 },
  road: { color: 0xa8a39a, roughness: 1 },
  roadDetail: { color: 0xc6c0b5, roughness: 0.96 },
  roofBlue: { color: 0x526b7a, roughness: 0.9 },
  roofGreen: { color: 0x667c5b, roughness: 0.92 },
  roofRed: { color: 0xa45345, roughness: 0.9 },
  shadow: { color: 0x536153, roughness: 1 },
  skin: { color: 0xd9a17d, roughness: 0.88 },
  trouser: { color: 0x172033, roughness: 0.9 },
  trunk: { color: 0x74543d, roughness: 1 },
  wallCool: { color: 0xc8d2d0, roughness: 0.94 },
  wallStone: { color: 0xb9b4aa, roughness: 1 },
  wallWarm: { color: 0xe7e7e1, roughness: 0.94 },
  water: { color: 0x688e9c, roughness: 0.34, metalness: 0.02 },
  white: { color: 0xe7e7e1, roughness: 0.9 },
  wood: { color: 0x76513e, roughness: 0.96 },
};

// Kept as a compatibility view for instance-color and planning code.
export const VOXEL_MATERIAL_COLORS = Object.fromEntries(
  Object.entries(VOXEL_MATERIAL_SPECS).map(([key, spec]) => [key, spec.color]),
) as Record<VoxelMaterialKey, number>;

export function getVoxelMaterialClass(material: VoxelMaterialKey): VoxelMaterialClass {
  if (material === "glass") return "glass";
  if (material === "water") return "water";
  if (material === "highlight") return "emissive";
  return "matte";
}

export const VOXEL_MATERIAL_CLASS_SPECS: Record<VoxelMaterialClass, VoxelMaterialSpec> = {
  matte: { color: 0xffffff, roughness: 0.9 },
  glass: {
    color: 0xffffff,
    roughness: 0.3,
    metalness: 0.02,
    emissive: 0xf2b45b,
    emissiveIntensity: 0.12,
  },
  water: { color: 0xffffff, roughness: 0.34, metalness: 0.02 },
  emissive: {
    color: 0xffffff,
    roughness: 0.74,
    emissive: 0xd86f45,
    emissiveIntensity: 0.08,
  },
};
