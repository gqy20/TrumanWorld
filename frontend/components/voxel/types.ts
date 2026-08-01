import type { SceneLocation } from "@/lib/world-scene-adapter";

export type VoxelPoint = {
  x: number;
  z: number;
};

export type VoxelSize = {
  width: number;
  depth: number;
};

export type VoxelVector3 = {
  x: number;
  y: number;
  z: number;
};

export type VoxelDistrict = "home" | "commerce" | "civic" | "green" | "center";

export type VoxelPlot = {
  id: string;
  locationId: string;
  locationType: string;
  district: VoxelDistrict;
  center: VoxelPoint;
  size: VoxelSize;
  footprint: VoxelSize;
  entrance: VoxelPoint;
  agentAnchors: VoxelPoint[];
  decorationAnchors: Array<VoxelPoint & { kind: string }>;
  source: SceneLocation;
};

export type VoxelMaterialKey =
  | "agent"
  | "agentMoving"
  | "agentResting"
  | "agentTalking"
  | "agentWorking"
  | "curb"
  | "flower"
  | "flowerPink"
  | "glass"
  | "grass"
  | "grassAlt"
  | "groundBase"
  | "hair"
  | "highlight"
  | "leaf"
  | "leafLight"
  | "plot"
  | "road"
  | "roadDetail"
  | "roofBlue"
  | "roofGreen"
  | "roofRed"
  | "shadow"
  | "skin"
  | "trouser"
  | "trunk"
  | "wallCool"
  | "wallStone"
  | "wallWarm"
  | "white"
  | "wood";

export type VoxelHitTarget = {
  kind: "agent" | "location";
  id: string;
};

export type VoxelBlock = {
  id: string;
  position: VoxelVector3;
  size: VoxelVector3;
  material: VoxelMaterialKey;
  castShadow: boolean;
  receiveShadow: boolean;
  hitTarget?: VoxelHitTarget;
};

export type VoxelBounds = {
  minX: number;
  maxX: number;
  minY: number;
  maxY: number;
  minZ: number;
  maxZ: number;
};

export type VoxelSelectionAnchor = {
  position: VoxelVector3;
  size: VoxelVector3;
};

export type VoxelScenePlan = {
  blocks: VoxelBlock[];
  bounds: VoxelBounds;
  plots: VoxelPlot[];
  locationAnchors: Record<string, VoxelSelectionAnchor>;
  agentAnchors: Record<string, VoxelSelectionAnchor>;
};
