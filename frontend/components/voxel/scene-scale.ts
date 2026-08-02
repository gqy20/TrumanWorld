/** Shared scene proportions. One resident is roughly 0.9 display units tall. */
export const VOXEL_SCENE_SCALE = {
  activitySeatHeight: 0.16,
  activitySurfaceHeight: 0.42,
  agentAnchorY: 0.055,
  buildingPlinthHeight: 0.08,
  doorHeight: 0.82,
  hedgeHeight: 0.22,
  landscapeTerraceHeight: 0.12,
  plotHeight: 0.03,
  thresholdPathHeight: 0.024,
  roadCurbHeight: 0.035,
  roadCurbWidth: 0.98,
  roadSurfaceHeight: 0.035,
  roadSurfaceWidth: 0.86,
} as const;

/** A loose horseshoe reads as a gathering instead of a queue at busy entrances. */
export const VOXEL_AGENT_FORMATION_OFFSETS = [
  { x: -0.32, z: -0.08 },
  { x: 0.32, z: -0.08 },
  { x: -0.5, z: 0.2 },
  { x: 0.5, z: 0.2 },
  { x: -0.24, z: 0.42 },
  { x: 0.24, z: 0.42 },
] as const;

export const VOXEL_CONVERSATION_OFFSETS = [
  { x: -0.3, z: 0.04 },
  { x: 0.3, z: 0.04 },
  { x: -0.42, z: 0.3 },
  { x: 0.42, z: 0.3 },
  { x: 0, z: 0.46 },
] as const;

export const VOXEL_WORK_OFFSETS = [
  { x: -0.24, z: -0.27 },
  { x: 0.24, z: -0.27 },
  { x: 0, z: -0.18 },
] as const;

export const VOXEL_REST_OFFSETS = [
  { x: -0.56, z: -0.02 },
  { x: 0.56, z: -0.02 },
  { x: -0.48, z: 0.25 },
  { x: 0.48, z: 0.25 },
] as const;
