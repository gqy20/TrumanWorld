import type { VoxelBounds, VoxelVector3 } from "./types";

export const VOXEL_CAMERA_MIN_ZOOM = 0.72;
export const VOXEL_CAMERA_MAX_ZOOM = 2.4;

export type VoxelCameraFrame = {
  aspect: number;
  position: VoxelVector3;
  target: VoxelVector3;
  viewHeight: number;
};

export type VoxelCameraSubject = {
  position: VoxelVector3;
  rotationY: number;
  size: VoxelVector3;
};

export type VoxelCameraFocusRequest = {
  kind: "agent" | "location";
  id: string;
  revision: number;
};

export function calculateVoxelCameraFrame(
  bounds: VoxelBounds,
  viewport: { width: number; height: number },
  subjects: VoxelCameraSubject[] = [],
): VoxelCameraFrame {
  const spanX = Math.max(1, bounds.maxX - bounds.minX);
  const spanZ = Math.max(1, bounds.maxZ - bounds.minZ);
  const aspect = viewport.width / Math.max(1, viewport.height);
  const cameraDirection = normalize({ x: 1, y: resolveCameraElevation(aspect), z: 1 });
  const cameraForward = scale(cameraDirection, -1);
  const cameraRight = normalize(cross(cameraForward, { x: 0, y: 1, z: 0 }));
  const cameraUp = normalize(cross(cameraRight, cameraForward));
  const projected = projectCameraSubjects(
    subjects.length > 0 ? subjects : [boundsToSubject(bounds)],
    cameraRight,
    cameraUp,
  );
  const padding = resolveFramePadding(viewport);
  const usableWidthRatio = Math.max(
    0.5,
    (viewport.width - padding.horizontal * 2) / Math.max(1, viewport.width),
  );
  const usableHeightRatio = Math.max(
    0.5,
    (viewport.height - padding.top - padding.bottom) / Math.max(1, viewport.height),
  );
  const projectedWidth = Math.max(1, projected.maxRight - projected.minRight);
  const projectedHeight = Math.max(1, projected.maxUp - projected.minUp);
  const viewHeight = Math.max(
    projectedHeight / usableHeightRatio,
    projectedWidth / (Math.max(0.35, aspect) * usableWidthRatio),
  ) * 1.02;
  const baseCenter = {
    x: (bounds.minX + bounds.maxX) / 2,
    y: (bounds.minY + bounds.maxY) / 2,
    z: (bounds.minZ + bounds.maxZ) / 2,
  };
  const projectedCenterRight = (projected.minRight + projected.maxRight) / 2;
  const projectedCenterUp = (projected.minUp + projected.maxUp) / 2;
  const baseCenterRight = dot(baseCenter, cameraRight);
  const baseCenterUp = dot(baseCenter, cameraUp);
  const safeAreaBias = ((padding.top - padding.bottom) / 2 / Math.max(1, viewport.height))
    * viewHeight;
  const target = add(
    add(
      baseCenter,
      scale(cameraRight, projectedCenterRight - baseCenterRight),
    ),
    scale(cameraUp, projectedCenterUp - baseCenterUp + safeAreaBias),
  );
  const distance = Math.max(spanX, spanZ, 10) * 1.05;
  const position = add(target, scale(cameraDirection, distance));

  return {
    aspect,
    position,
    target,
    viewHeight,
  };
}

function projectCameraSubjects(
  subjects: VoxelCameraSubject[],
  cameraRight: VoxelVector3,
  cameraUp: VoxelVector3,
): { maxRight: number; maxUp: number; minRight: number; minUp: number } {
  const projection = {
    maxRight: Number.NEGATIVE_INFINITY,
    maxUp: Number.NEGATIVE_INFINITY,
    minRight: Number.POSITIVE_INFINITY,
    minUp: Number.POSITIVE_INFINITY,
  };
  for (const subject of subjects) {
    const cos = Math.cos(subject.rotationY);
    const sin = Math.sin(subject.rotationY);
    for (const xSign of [-1, 1]) {
      for (const ySign of [-1, 1]) {
        for (const zSign of [-1, 1]) {
          const localX = xSign * subject.size.x / 2;
          const localZ = zSign * subject.size.z / 2;
          const point = {
            x: subject.position.x + localX * cos + localZ * sin,
            y: subject.position.y + ySign * subject.size.y / 2,
            z: subject.position.z - localX * sin + localZ * cos,
          };
          const right = dot(point, cameraRight);
          const up = dot(point, cameraUp);
          projection.minRight = Math.min(projection.minRight, right);
          projection.maxRight = Math.max(projection.maxRight, right);
          projection.minUp = Math.min(projection.minUp, up);
          projection.maxUp = Math.max(projection.maxUp, up);
        }
      }
    }
  }
  return projection;
}

function boundsToSubject(bounds: VoxelBounds): VoxelCameraSubject {
  return {
    position: {
      x: (bounds.minX + bounds.maxX) / 2,
      y: (bounds.minY + bounds.maxY) / 2,
      z: (bounds.minZ + bounds.maxZ) / 2,
    },
    rotationY: 0,
    size: {
      x: Math.max(1, bounds.maxX - bounds.minX),
      y: Math.max(1, bounds.maxY - bounds.minY),
      z: Math.max(1, bounds.maxZ - bounds.minZ),
    },
  };
}

function resolveFramePadding(viewport: { width: number; height: number }): {
  bottom: number;
  horizontal: number;
  top: number;
} {
  if (viewport.width < 640) return { bottom: 48, horizontal: 16, top: 48 };
  return { bottom: 48, horizontal: 32, top: 48 };
}

function resolveCameraElevation(aspect: number): number {
  if (aspect < 1.05) return 2.2;
  if (aspect < 1.4) return 1.35;
  return 0.85;
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

function add(left: VoxelVector3, right: VoxelVector3): VoxelVector3 {
  return { x: left.x + right.x, y: left.y + right.y, z: left.z + right.z };
}

function cross(left: VoxelVector3, right: VoxelVector3): VoxelVector3 {
  return {
    x: left.y * right.z - left.z * right.y,
    y: left.z * right.x - left.x * right.z,
    z: left.x * right.y - left.y * right.x,
  };
}

function dot(left: VoxelVector3, right: VoxelVector3): number {
  return left.x * right.x + left.y * right.y + left.z * right.z;
}

function normalize(vector: VoxelVector3): VoxelVector3 {
  const length = Math.hypot(vector.x, vector.y, vector.z) || 1;
  return scale(vector, 1 / length);
}

function scale(vector: VoxelVector3, factor: number): VoxelVector3 {
  return { x: vector.x * factor, y: vector.y * factor, z: vector.z * factor };
}
