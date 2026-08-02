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
const CORNER_RADIUS = 0.22;
const CORNER_SUBDIVISIONS = 4;

export function buildVoxelMotionPath(points: VoxelVector3[]): VoxelMotionPath {
  const deduped = points.filter((point, index) => {
    const previous = points[index - 1];
    return !previous || distanceBetween(previous, point) > Number.EPSILON;
  });
  const smoothed = roundPathCorners(deduped);
  const cumulativeLengths = [0];
  for (let index = 1; index < smoothed.length; index += 1) {
    cumulativeLengths.push(
      cumulativeLengths[index - 1] + distanceBetween(smoothed[index - 1], smoothed[index]),
    );
  }
  return {
    points: smoothed,
    cumulativeLengths,
    totalLength: cumulativeLengths.at(-1) ?? 0,
  };
}

/** Adds restrained acceleration and deceleration without delaying the midpoint. */
export function easeVoxelMotionProgress(progress: number): number {
  const clamped = clamp(progress, 0, 1);
  return clamp(clamped - 0.1 * Math.sin(Math.PI * 2 * clamped), 0, 1);
}

/** Fades limb motion in and out while the root continues moving. */
export function calculateVoxelGaitStrength(progress: number): number {
  return Math.sin(Math.PI * clamp(progress, 0, 1));
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

export function advanceVoxelMotionProgress(
  progress: number,
  durationMs: number,
  deltaSeconds: number,
  isPaused: boolean,
): number {
  const current = clamp(progress, 0, 1);
  if (isPaused || durationMs <= 0 || deltaSeconds <= 0) return current;
  return clamp(current + (deltaSeconds * 1000) / durationMs, 0, 1);
}

function findSegmentIndex(cumulativeLengths: number[], distance: number): number {
  for (let index = 0; index < cumulativeLengths.length - 1; index += 1) {
    if (distance <= cumulativeLengths[index + 1]) return index;
  }
  return Math.max(0, cumulativeLengths.length - 2);
}

function roundPathCorners(points: VoxelVector3[]): VoxelVector3[] {
  if (points.length < 3) return points;
  const rounded = [{ ...points[0] }];
  for (let index = 1; index < points.length - 1; index += 1) {
    const previous = points[index - 1];
    const corner = points[index];
    const next = points[index + 1];
    const incoming = normalize(subtract(corner, previous));
    const outgoing = normalize(subtract(next, corner));
    const alignment = incoming.x * outgoing.x
      + incoming.y * outgoing.y
      + incoming.z * outgoing.z;
    if (Math.abs(alignment) > 0.999) {
      rounded.push({ ...corner });
      continue;
    }

    const radius = Math.min(
      CORNER_RADIUS,
      distanceBetween(previous, corner) * 0.3,
      distanceBetween(corner, next) * 0.3,
    );
    const entry = add(corner, scale(incoming, -radius));
    const exit = add(corner, scale(outgoing, radius));
    rounded.push(entry);
    for (let step = 1; step <= CORNER_SUBDIVISIONS; step += 1) {
      const progress = step / CORNER_SUBDIVISIONS;
      rounded.push(quadraticBezier(entry, corner, exit, progress));
    }
  }
  rounded.push({ ...points.at(-1)! });
  return rounded.filter((point, index, allPoints) => {
    const previous = allPoints[index - 1];
    return !previous || distanceBetween(previous, point) > Number.EPSILON;
  });
}

function quadraticBezier(
  start: VoxelVector3,
  control: VoxelVector3,
  end: VoxelVector3,
  progress: number,
): VoxelVector3 {
  const inverse = 1 - progress;
  return {
    x: inverse * inverse * start.x + 2 * inverse * progress * control.x
      + progress * progress * end.x,
    y: inverse * inverse * start.y + 2 * inverse * progress * control.y
      + progress * progress * end.y,
    z: inverse * inverse * start.z + 2 * inverse * progress * control.z
      + progress * progress * end.z,
  };
}

function subtract(left: VoxelVector3, right: VoxelVector3): VoxelVector3 {
  return { x: left.x - right.x, y: left.y - right.y, z: left.z - right.z };
}

function add(left: VoxelVector3, right: VoxelVector3): VoxelVector3 {
  return { x: left.x + right.x, y: left.y + right.y, z: left.z + right.z };
}

function scale(vector: VoxelVector3, factor: number): VoxelVector3 {
  return { x: vector.x * factor, y: vector.y * factor, z: vector.z * factor };
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
