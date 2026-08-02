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

export type VoxelLocomotionState = {
  distance: number;
  speed: number;
};

export type VoxelLocomotionOptions = {
  acceleration?: number;
  authoritativeDistance?: number;
  deceleration?: number;
  maxSpeed: number;
};

export type VoxelAvoidanceNeighbor = {
  id: string;
  position: VoxelVector3;
};

export type VoxelJunctionCheckpoint = {
  distance: number;
  id: string;
};

export type VoxelJunctionAgentState = {
  agentId: string;
  distance: number;
  formationId: string;
  junctions: VoxelJunctionCheckpoint[];
};

const DEFAULT_ACCELERATION = 2.8;
const DEFAULT_DECELERATION = 3.8;
const MAX_FRAME_DELTA_SECONDS = 0.1;
const CORNER_RADIUS = 0.28;
const CORNER_SUBDIVISIONS = 6;
const WALKING_SPEED_VARIANTS = 9;
const JUNCTION_APPROACH_DISTANCE = 0.85;
const JUNCTION_CLEAR_DISTANCE = 0.32;

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

export function resolveVoxelWalkingSpeed(agentId: string, baseSpeed = 1.5): number {
  let hash = 0;
  for (const character of agentId) hash = (hash * 31 + character.charCodeAt(0)) >>> 0;
  const variation = 0.9 + (hash % WALKING_SPEED_VARIANTS) * 0.025;
  return Math.max(0.1, baseSpeed) * variation;
}

/** Advances physical distance using acceleration and a braking-speed envelope. */
export function advanceVoxelLocomotion(
  path: VoxelMotionPath,
  state: VoxelLocomotionState,
  deltaSeconds: number,
  options: VoxelLocomotionOptions,
): VoxelLocomotionState {
  if (path.totalLength <= 0 || deltaSeconds <= 0) {
    return { distance: clamp(state.distance, 0, path.totalLength), speed: 0 };
  }
  const delta = Math.min(deltaSeconds, MAX_FRAME_DELTA_SECONDS);
  const distance = clamp(state.distance, 0, path.totalLength);
  const remaining = path.totalLength - distance;
  if (remaining <= Number.EPSILON) return { distance: path.totalLength, speed: 0 };

  const acceleration = options.acceleration ?? DEFAULT_ACCELERATION;
  const deceleration = options.deceleration ?? DEFAULT_DECELERATION;
  const authoritativeGap = Math.max(0, (options.authoritativeDistance ?? distance) - distance);
  const catchUpScale = 1 + clamp(authoritativeGap * 0.24, 0, 0.28);
  const cruiseSpeed = options.maxSpeed * catchUpScale;
  const brakingSpeed = Math.sqrt(2 * deceleration * remaining);
  const desiredSpeed = Math.min(cruiseSpeed, brakingSpeed);
  const rate = desiredSpeed >= state.speed ? acceleration : deceleration;
  const nextSpeed = moveTowards(Math.max(0, state.speed), desiredSpeed, rate * delta);
  const travelled = Math.min(remaining, (Math.max(0, state.speed) + nextSpeed) * 0.5 * delta);
  const nextDistance = distance + travelled;
  return {
    distance: nextDistance,
    speed: nextDistance >= path.totalLength - Number.EPSILON ? 0 : nextSpeed,
  };
}

/** Couples gait amplitude to actual root velocity, including natural start and stop settling. */
export function calculateVoxelGaitStrength(speed: number, maxSpeed: number): number {
  if (maxSpeed <= 0) return 0;
  const normalized = clamp((speed / maxSpeed) * 1.3, 0, 1);
  return normalized * normalized * (3 - 2 * normalized);
}

export function calculateVoxelStridePhase(distance: number): number {
  const strideLength = 0.52;
  return (Math.max(0, distance) / strideLength) * Math.PI * 2;
}

export function calculateVoxelLookAheadDistance(speed: number): number {
  return clamp(0.14 + Math.max(0, speed) * 0.16, 0.14, 0.4);
}

export function sampleVoxelMotionPath(path: VoxelMotionPath, progress: number): VoxelMotionSample {
  return sampleVoxelMotionPathAtDistance(path, clamp(progress, 0, 1) * path.totalLength);
}

export function sampleVoxelMotionPathAtDistance(
  path: VoxelMotionPath,
  requestedDistance: number,
): VoxelMotionSample {
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

  const distance = clamp(requestedDistance, 0, path.totalLength);
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

export function offsetVoxelMotionSample(
  path: VoxelMotionPath,
  distance: number,
  sample: VoxelMotionSample,
  laneOffset: number,
  longitudinalOffset: number,
): VoxelMotionSample {
  if (path.totalLength <= 0) return sample;
  const laneBlend = calculateVoxelEndpointBlend(distance, path.totalLength, 0.65);
  const followingBlend = calculateVoxelEndpointBlend(distance, path.totalLength, 1.15);
  const right = { x: sample.tangent.z, y: 0, z: -sample.tangent.x };
  return {
    ...sample,
    position: add(
      add(sample.position, scale(right, laneOffset * laneBlend)),
      scale(sample.tangent, -longitudinalOffset * followingBlend),
    ),
  };
}

/** Projects a world-space marker onto the closest point of a travelled path. */
export function findNearestVoxelPathDistance(
  path: VoxelMotionPath,
  marker: VoxelVector3,
): number {
  if (path.points.length < 2) return 0;
  let nearestDistance = 0;
  let nearestDistanceSquared = Number.POSITIVE_INFINITY;
  for (let index = 0; index < path.points.length - 1; index += 1) {
    const start = path.points[index];
    const end = path.points[index + 1];
    const segment = subtract(end, start);
    const lengthSquared = segment.x ** 2 + segment.y ** 2 + segment.z ** 2;
    if (lengthSquared <= Number.EPSILON) continue;
    const toMarker = subtract(marker, start);
    const progress = clamp(
      (toMarker.x * segment.x + toMarker.y * segment.y + toMarker.z * segment.z)
        / lengthSquared,
      0,
      1,
    );
    const projected = add(start, scale(segment, progress));
    const distanceSquared = (projected.x - marker.x) ** 2
      + (projected.y - marker.y) ** 2
      + (projected.z - marker.z) ** 2;
    if (distanceSquared >= nearestDistanceSquared) continue;
    nearestDistanceSquared = distanceSquared;
    nearestDistance = path.cumulativeLengths[index] + Math.sqrt(lengthSquared) * progress;
  }
  return nearestDistance;
}

/**
 * Resolves stable right-of-way for residents approaching the same junction.
 * A formation is treated as one party, while somebody already crossing keeps priority.
 */
export function resolveVoxelJunctionSpeedScales(
  states: VoxelJunctionAgentState[],
): Map<string, number> {
  const scales = new Map(states.map((state) => [state.agentId, 1]));
  const approachesByJunction = new Map<
    string,
    Array<VoxelJunctionAgentState & { signedDistance: number }>
  >();
  for (const state of states) {
    for (const junction of state.junctions) {
      const signedDistance = junction.distance - state.distance;
      if (
        signedDistance < -JUNCTION_CLEAR_DISTANCE
        || signedDistance > JUNCTION_APPROACH_DISTANCE
      ) continue;
      const approaches = approachesByJunction.get(junction.id) ?? [];
      approaches.push({ ...state, signedDistance });
      approachesByJunction.set(junction.id, approaches);
    }
  }

  for (const approaches of approachesByJunction.values()) {
    const formations = new Map<string, typeof approaches>();
    for (const approach of approaches) {
      const members = formations.get(approach.formationId) ?? [];
      members.push(approach);
      formations.set(approach.formationId, members);
    }
    if (formations.size < 2) continue;
    const parties = Array.from(formations, ([formationId, members]) => ({
      formationId,
      members,
      signedDistance: Math.min(...members.map((member) => member.signedDistance)),
    }));
    parties.sort((left, right) => {
      const leftCommitted = left.signedDistance <= 0;
      const rightCommitted = right.signedDistance <= 0;
      if (leftCommitted !== rightCommitted) return leftCommitted ? -1 : 1;
      if (leftCommitted && rightCommitted) return left.signedDistance - right.signedDistance;
      return left.formationId.localeCompare(right.formationId);
    });
    const winner = parties[0].formationId;
    for (const party of parties) {
      if (party.formationId === winner) continue;
      for (const member of party.members) {
        if (member.signedDistance <= 0) continue;
        const approachProgress = clamp(
          member.signedDistance / JUNCTION_APPROACH_DISTANCE,
          0,
          1,
        );
        const scaleAtJunction = 0.12;
        const yieldScale = scaleAtJunction
          + (1 - scaleAtJunction) * approachProgress * approachProgress;
        scales.set(member.agentId, Math.min(scales.get(member.agentId) ?? 1, yieldScale));
      }
    }
  }
  return scales;
}

export function calculateVoxelAvoidanceOffset(
  agentId: string,
  position: VoxelVector3,
  neighbors: VoxelAvoidanceNeighbor[],
  personalSpace = 0.42,
  maximumOffset = 0.1,
): VoxelVector3 {
  if (personalSpace <= 0 || maximumOffset <= 0) return { x: 0, y: 0, z: 0 };
  let offset = { x: 0, y: 0, z: 0 };
  for (const neighbor of neighbors) {
    if (neighbor.id === agentId) continue;
    const delta = {
      x: position.x - neighbor.position.x,
      y: 0,
      z: position.z - neighbor.position.z,
    };
    const distance = Math.hypot(delta.x, delta.z);
    if (distance >= personalSpace) continue;
    const direction = distance > Number.EPSILON
      ? scale(delta, 1 / distance)
      : resolveCoincidentDirection(agentId, neighbor.id);
    const pressure = (1 - distance / personalSpace) ** 2;
    offset = add(offset, scale(direction, pressure * maximumOffset));
  }
  const length = Math.hypot(offset.x, offset.z);
  return length > maximumOffset ? scale(offset, maximumOffset / length) : offset;
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

function moveTowards(current: number, target: number, maximumDelta: number): number {
  if (Math.abs(target - current) <= maximumDelta) return target;
  return current + Math.sign(target - current) * maximumDelta;
}

export function calculateVoxelEndpointBlend(
  distance: number,
  totalLength: number,
  maximumFadeDistance = 0.65,
): number {
  const fadeDistance = Math.min(maximumFadeDistance, totalLength * 0.22);
  if (fadeDistance <= Number.EPSILON) return 0;
  const endpointDistance = Math.min(distance, totalLength - distance);
  const progress = clamp(endpointDistance / fadeDistance, 0, 1);
  return progress * progress * (3 - 2 * progress);
}

function resolveCoincidentDirection(agentId: string, neighborId: string): VoxelVector3 {
  const first = agentId < neighborId ? agentId : neighborId;
  const second = agentId < neighborId ? neighborId : agentId;
  let hash = 0;
  for (const character of `${first}:${second}`) {
    hash = (hash * 31 + character.charCodeAt(0)) >>> 0;
  }
  const angle = (hash % 360) * Math.PI / 180;
  const sign = agentId === first ? 1 : -1;
  return { x: Math.cos(angle) * sign, y: 0, z: Math.sin(angle) * sign };
}
