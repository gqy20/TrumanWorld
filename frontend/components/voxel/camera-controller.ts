import type { VoxelBounds, VoxelVector3 } from "./types";

export const VOXEL_CAMERA_MIN_ZOOM = 0.72;
export const VOXEL_CAMERA_MAX_ZOOM = 2.4;

export type VoxelCameraFrame = {
  aspect: number;
  position: VoxelVector3;
  target: VoxelVector3;
  viewHeight: number;
};

export type VoxelCameraFocusRequest = {
  kind: "agent" | "location";
  id: string;
  revision: number;
};

export function calculateVoxelCameraFrame(
  bounds: VoxelBounds,
  viewport: { width: number; height: number },
): VoxelCameraFrame {
  const centerX = (bounds.minX + bounds.maxX) / 2;
  const centerZ = (bounds.minZ + bounds.maxZ) / 2;
  const spanX = Math.max(1, bounds.maxX - bounds.minX);
  const spanZ = Math.max(1, bounds.maxZ - bounds.minZ);
  const spanY = Math.max(1, bounds.maxY - bounds.minY);
  const aspect = viewport.width / Math.max(1, viewport.height);
  const projectedWidth = (spanX + spanZ) * 0.72;
  const projectedHeight = (spanX + spanZ) * 0.34 + spanY;
  const viewHeight =
    Math.max(projectedHeight, projectedWidth / Math.max(0.35, aspect)) * 1.12;
  const distance = Math.max(spanX, spanZ, 10) * 0.9;

  return {
    aspect,
    position: {
      x: centerX + distance,
      y: distance * 0.85,
      z: centerZ + distance,
    },
    target: {
      x: centerX,
      y: Math.max(0.2, spanY * 0.16),
      z: centerZ,
    },
    viewHeight,
  };
}

export function calculateVoxelCameraZoom(currentZoom: number, wheelDeltaY: number): number {
  return clampVoxelCameraZoom(currentZoom * Math.exp(-wheelDeltaY * 0.0014));
}

export function clampVoxelCameraZoom(zoom: number): number {
  return Math.min(VOXEL_CAMERA_MAX_ZOOM, Math.max(VOXEL_CAMERA_MIN_ZOOM, zoom));
}

export function easeOutQuint(progress: number): number {
  const clamped = Math.min(1, Math.max(0, progress));
  return 1 - (1 - clamped) ** 5;
}
