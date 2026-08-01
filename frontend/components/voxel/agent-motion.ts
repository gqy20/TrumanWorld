import type { VoxelVector3 } from "./types";

export type VoxelMotionPath = {
  points: VoxelVector3[];
  cumulativeLengths: number[];
  totalLength: number;
};

export type VoxelMotionSample = {
  position: VoxelVector3;
  tangent: VoxelVector3;
};

const DEFAULT_SPEED_UNITS_PER_SECOND = 2.2;
const MIN_DURATION_MS = 900;
const MAX_DURATION_MS = 4800;

export function buildVoxelMotionPath(points: VoxelVector3[]): VoxelMotionPath {
  const deduped = points.filter((point, index) => {
    const previous = points[index - 1];
    return !previous || distanceBetween(previous, point) > Number.EPSILON;
  });
  const cumulativeLengths = [0];
  for (let index = 1; index < deduped.length; index += 1) {
    cumulativeLengths.push(
      cumulativeLengths[index - 1] + distanceBetween(deduped[index - 1], deduped[index]),
    );
  }
  return {
    points: deduped,
    cumulativeLengths,
    totalLength: cumulativeLengths.at(-1) ?? 0,
  };
}

export function sampleVoxelMotionPath(path: VoxelMotionPath, progress: number): VoxelMotionSample {
  if (path.points.length === 0) {
    return {
      position: { x: 0, y: 0, z: 0 },
      tangent: { x: 0, y: 0, z: 1 },
    };
  }
  if (path.points.length === 1 || path.totalLength === 0) {
    return {
      position: { ...path.points[0] },
      tangent: { x: 0, y: 0, z: 1 },
    };
  }

  const distance = clamp(progress, 0, 1) * path.totalLength;
  const segmentIndex = findSegmentIndex(path.cumulativeLengths, distance);
  const start = path.points[segmentIndex];
  const end = path.points[segmentIndex + 1];
  const segmentStart = path.cumulativeLengths[segmentIndex];
  const segmentLength = path.cumulativeLengths[segmentIndex + 1] - segmentStart;
  const segmentProgress = segmentLength === 0 ? 0 : (distance - segmentStart) / segmentLength;

  return {
    position: {
      x: start.x + (end.x - start.x) * segmentProgress,
      y: start.y + (end.y - start.y) * segmentProgress,
      z: start.z + (end.z - start.z) * segmentProgress,
    },
    tangent: normalize({
      x: end.x - start.x,
      y: end.y - start.y,
      z: end.z - start.z,
    }),
  };
}

export function calculateVoxelMotionDuration(
  pathLength: number,
  speedUnitsPerSecond = DEFAULT_SPEED_UNITS_PER_SECOND,
): number {
  if (pathLength <= 0 || speedUnitsPerSecond <= 0) return 0;
  return clamp((pathLength / speedUnitsPerSecond) * 1000, MIN_DURATION_MS, MAX_DURATION_MS);
}

function findSegmentIndex(cumulativeLengths: number[], distance: number): number {
  for (let index = 0; index < cumulativeLengths.length - 1; index += 1) {
    if (distance <= cumulativeLengths[index + 1]) return index;
  }
  return Math.max(0, cumulativeLengths.length - 2);
}

function distanceBetween(left: VoxelVector3, right: VoxelVector3): number {
  return Math.hypot(right.x - left.x, right.y - left.y, right.z - left.z);
}

function normalize(vector: VoxelVector3): VoxelVector3 {
  const length = Math.hypot(vector.x, vector.y, vector.z);
  if (length === 0) return { x: 0, y: 0, z: 1 };
  return { x: vector.x / length, y: vector.y / length, z: vector.z / length };
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(maximum, Math.max(minimum, value));
}
