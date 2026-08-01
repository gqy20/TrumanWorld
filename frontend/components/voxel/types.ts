import type { SceneAgent, SceneLocation } from "@/lib/world-scene-adapter";

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
  | "paving"
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
  | "water"
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
  rotationY: number;
  castShadow: boolean;
  receiveShadow: boolean;
  hitTarget?: VoxelHitTarget;
};

export type VoxelPrefabBlock = {
  position: VoxelVector3;
  size: VoxelVector3;
  material: VoxelMaterialKey;
  rotationY?: number;
  castShadow?: boolean;
  receiveShadow?: boolean;
};

export type VoxelPrefab = {
  kind: "cafe" | "generic" | "green" | "home" | "hospital" | "library" | "office" | "plaza";
  blocks: VoxelPrefabBlock[];
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

export type VoxelAgentPlan = {
  id: string;
  source: SceneAgent;
  anchor: VoxelSelectionAnchor;
};

export type VoxelRoadConnections = {
  north: boolean;
  east: boolean;
  south: boolean;
  west: boolean;
};

export type VoxelRoadTile = VoxelPoint & {
  role: "connector" | "main" | "plaza";
  connections: VoxelRoadConnections;
};

export type VoxelScenePlan = {
  blocks: VoxelBlock[];
  agents: VoxelAgentPlan[];
  bounds: VoxelBounds;
  plots: VoxelPlot[];
  roads: VoxelRoadTile[];
  locationAnchors: Record<string, VoxelSelectionAnchor>;
  agentAnchors: Record<string, VoxelSelectionAnchor>;
};
