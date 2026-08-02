import type { SceneAgent, SceneLocation } from "@/lib/world-scene-adapter";
import type { VoxelAgentAppearance } from "./agent-appearance";

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
  activityAnchors: {
    talking: VoxelPoint[];
    working: VoxelPoint[];
    resting: VoxelPoint[];
  };
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

export type VoxelGeometryKind = "box" | "cone" | "cylinder" | "icosphere";

export type VoxelBlock = {
  id: string;
  position: VoxelVector3;
  size: VoxelVector3;
  material: VoxelMaterialKey;
  geometry: VoxelGeometryKind;
  rotationY: number;
  castShadow: boolean;
  receiveShadow: boolean;
  layer: "ambient" | "core";
  hitTarget?: VoxelHitTarget;
};

export type VoxelBlockWriter = (
  prefix: string,
  position: [number, number, number],
  size: [number, number, number],
  material: VoxelMaterialKey,
  options?: {
    castShadow?: boolean;
    receiveShadow?: boolean;
    hitTarget?: VoxelHitTarget;
    layer?: VoxelBlock["layer"];
    rotationY?: number;
    geometry?: VoxelGeometryKind;
  },
) => VoxelBlock;

export type VoxelPrefabBlock = {
  position: VoxelVector3;
  size: VoxelVector3;
  material: VoxelMaterialKey;
  geometry?: VoxelGeometryKind;
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
  appearance: VoxelAgentAppearance;
  rotationY: number;
};

export type VoxelAssetPlacement = {
  assetId: string;
  fallbackBlocks: VoxelBlock[];
  locationId: string;
  position: VoxelVector3;
  rotationY: number;
  scale: VoxelVector3;
  uri: `/world/${string}.glb`;
};

export type VoxelRoadConnections = {
  north: boolean;
  east: boolean;
  south: boolean;
  west: boolean;
};

export type VoxelRoadTile = VoxelPoint & {
  nodeId?: string;
  role: "connector" | "main" | "plaza";
  connections: VoxelRoadConnections;
};

export type VoxelScenePlan = {
  blocks: VoxelBlock[];
  assets: VoxelAssetPlacement[];
  agents: VoxelAgentPlan[];
  bounds: VoxelBounds;
  focusBounds: VoxelBounds;
  plots: VoxelPlot[];
  roads: VoxelRoadTile[];
  locationAnchors: Record<string, VoxelSelectionAnchor>;
  agentAnchors: Record<string, VoxelSelectionAnchor>;
};
