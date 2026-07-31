import type { SceneLocation } from "@/lib/world-scene-adapter";

export type VoxelPoint = {
  x: number;
  z: number;
};

export type VoxelSize = {
  width: number;
  depth: number;
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
