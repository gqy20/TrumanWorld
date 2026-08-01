import type { VoxelDistrict, VoxelSize } from "./types";

export type VoxelLocationSpec = {
  district: VoxelDistrict;
  size: VoxelSize;
  footprint: VoxelSize;
};

const DEFAULT_SPEC: VoxelLocationSpec = {
  district: "civic",
  size: { width: 1.8, depth: 1.8 },
  footprint: { width: 1.25, depth: 1.25 },
};

const LOCATION_SPECS: Record<string, VoxelLocationSpec> = {
  home: spec("home", 1.7, 1.7, 1.2, 1.2),
  dorm: spec("home", 1.8, 1.8, 1.3, 1.3),
  cafe: spec("commerce", 1.7, 1.7, 1.25, 1.25),
  shop: spec("commerce", 1.8, 1.8, 1.3, 1.3),
  plaza: spec("center", 1.8, 1.8, 0.9, 0.9),
  square: spec("center", 1.8, 1.8, 0.9, 0.9),
  office: spec("civic", 1.8, 1.8, 1.3, 1.3),
  library: spec("civic", 1.8, 1.8, 1.35, 1.25),
  lecture_hall: spec("civic", 1.8, 1.8, 1.4, 1.2),
  hospital: spec("civic", 1.8, 1.8, 1.35, 1.35),
  park: spec("green", 1.8, 1.8, 0.7, 0.7),
  grove: spec("green", 1.8, 1.8, 0.7, 0.7),
  quad: spec("green", 1.8, 1.8, 0.7, 0.7),
};

export function resolveVoxelLocationSpec(
  locationType: string,
  visualPreset?: string,
): VoxelLocationSpec {
  return LOCATION_SPECS[locationType] ??
    (visualPreset ? LOCATION_SPECS[visualPreset] : undefined) ??
    DEFAULT_SPEC;
}

function spec(
  district: VoxelDistrict,
  width: number,
  depth: number,
  footprintWidth: number,
  footprintDepth: number,
): VoxelLocationSpec {
  return {
    district,
    size: { width, depth },
    footprint: { width: footprintWidth, depth: footprintDepth },
  };
}
