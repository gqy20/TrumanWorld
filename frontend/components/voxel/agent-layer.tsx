"use client";

import { type ThreeEvent, useFrame, useThree } from "@react-three/fiber";
import { type MutableRefObject, useEffect, useLayoutEffect, useMemo, useRef } from "react";
import * as THREE from "three";

import {
  buildVoxelAgentInstanceParts,
  type VoxelAgentGeometryKind,
  type VoxelAgentInstancePart,
  VOXEL_AGENT_GEOMETRY_KINDS,
} from "./agent-instances";
import {
  advanceVoxelLocomotion,
  buildVoxelMotionPath,
  calculateVoxelAvoidanceOffset,
  calculateVoxelEndpointBlend,
  calculateVoxelGaitStrength,
  calculateVoxelLookAheadDistance,
  calculateVoxelStridePhase,
  findNearestVoxelPathDistance,
  resolveVoxelJunctionSpeedScales,
  resolveVoxelWalkingSpeed,
  offsetVoxelMotionSample,
  sampleVoxelMotionPath,
  sampleVoxelMotionPathAtDistance,
  type VoxelMotionPath,
} from "./agent-motion";
import type { VoxelMovementFormation, VoxelMoveTrail } from "./event-plan";
import type { VoxelAgentPlan } from "./types";

export type AgentPoseMap = MutableRefObject<Map<string, THREE.Vector3>>;

type AgentAnimation = {
  arrivalRotationY: number;
  authoritativeDistance: number;
  distance: number;
  eventId: string;
  formation: VoxelMovementFormation;
  junctions: Array<{ distance: number; id: string }>;
  path: VoxelMotionPath;
  skipNextFrame: boolean;
  speed: number;
  walkingSpeed: number;
};

type AgentRuntime = {
  animation: AgentAnimation | null;
  avoidanceOffset: THREE.Vector3;
  avoidanceTarget: THREE.Vector3;
  avoidanceWeight: number;
  basePosition: THREE.Vector3;
  bodyBob: number;
  completedMotionId: string | null;
  gaitSwing: number;
  position: THREE.Vector3;
  rotationY: number;
};

type AgentPartBatch = {
  geometry: VoxelAgentGeometryKind;
  parts: VoxelAgentInstancePart[];
};

export function AgentLayer({
  agents,
  moveTrails,
  poseMap,
  isPaused,
  prefersReducedMotion,
  onAgentClick,
}: {
  agents: VoxelAgentPlan[];
  moveTrails: VoxelMoveTrail[];
  poseMap: AgentPoseMap;
  isPaused: boolean;
  prefersReducedMotion: boolean;
  onAgentClick?: (agentId: string) => void;
}) {
  const meshRefs = useRef<Partial<Record<VoxelAgentGeometryKind, THREE.InstancedMesh>>>({});
  const runtimesRef = useRef<Map<string, AgentRuntime>>(new Map());
  const previousPausedRef = useRef(isPaused);
  const transformRef = useRef({ root: new THREE.Object3D(), part: new THREE.Object3D() });
  const invalidate = useThree((state) => state.invalidate);
  const parts = useMemo(() => buildVoxelAgentInstanceParts(agents), [agents]);
  const batches = useMemo<AgentPartBatch[]>(
    () =>
      VOXEL_AGENT_GEOMETRY_KINDS.map((geometry) => ({
        geometry,
        parts: parts.filter((part) => part.geometry === geometry),
      })).filter((batch) => batch.parts.length > 0),
    [parts],
  );
  const material = useMemo(
    () => new THREE.MeshStandardMaterial({ color: 0xffffff, metalness: 0, roughness: 0.84 }),
    [],
  );
  const motionByAgentId = useMemo(() => {
    const motions = new Map<string, VoxelMoveTrail>();
    for (const trail of moveTrails) {
      if (trail.actorId && !motions.has(trail.actorId)) motions.set(trail.actorId, trail);
    }
    return motions;
  }, [moveTrails]);

  useLayoutEffect(() => {
    const wasPaused = previousPausedRef.current;
    previousPausedRef.current = isPaused;
    const activeAgentIds = new Set(agents.map((agent) => agent.id));
    for (const agentId of runtimesRef.current.keys()) {
      if (activeAgentIds.has(agentId)) continue;
      runtimesRef.current.delete(agentId);
      poseMap.current.delete(agentId);
    }

    for (const agent of agents) {
      const motion = motionByAgentId.get(agent.id);
      const runtime = getOrCreateRuntime(runtimesRef.current, agent);
      synchronizeAgentRuntime(
        runtime,
        agent,
        motion,
        isPaused,
        prefersReducedMotion,
        wasPaused,
      );
      publishAgentPose(poseMap, agent.id, runtime.position);
    }

    for (const batch of batches) {
      const mesh = meshRefs.current[batch.geometry];
      if (!mesh) continue;
      mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
      batch.parts.forEach((part, index) => mesh.setColorAt(index, new THREE.Color(part.color)));
      if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
      updateAgentInstanceMatrices(
        mesh,
        batch.parts,
        runtimesRef.current,
        transformRef.current,
      );
    }
    invalidate();
  }, [
    agents,
    batches,
    invalidate,
    isPaused,
    motionByAgentId,
    poseMap,
    prefersReducedMotion,
  ]);

  useEffect(
    () => () => {
      for (const agentId of runtimesRef.current.keys()) poseMap.current.delete(agentId);
    },
    [poseMap],
  );

  useEffect(() => () => material.dispose(), [material]);

  useFrame((_state, delta) => {
    if (isPaused) return;
    const { changed, needsNextFrame } = advanceAgentAnimations(
      runtimesRef.current,
      poseMap,
      delta,
    );
    if (changed) {
      for (const batch of batches) {
        const mesh = meshRefs.current[batch.geometry];
        if (!mesh) continue;
        updateAgentInstanceMatrices(
          mesh,
          batch.parts,
          runtimesRef.current,
          transformRef.current,
        );
      }
    }
    if (needsNextFrame) invalidate();
  });

  const handleClick = (event: ThreeEvent<MouseEvent>, batchParts: VoxelAgentInstancePart[]) => {
    const agentId =
      event.instanceId === undefined ? undefined : batchParts[event.instanceId]?.agentId;
    if (!agentId) return;
    event.stopPropagation();
    onAgentClick?.(agentId);
  };

  if (parts.length === 0) return null;
  return (
    <group>
      {batches.map((batch) => (
        <instancedMesh
          key={batch.geometry}
          ref={(mesh) => {
            if (mesh) meshRefs.current[batch.geometry] = mesh;
            else delete meshRefs.current[batch.geometry];
          }}
          args={[undefined, undefined, batch.parts.length]}
          material={material}
          castShadow
          receiveShadow
          frustumCulled={false}
          onClick={(event) => handleClick(event, batch.parts)}
        >
          <AgentPartGeometry kind={batch.geometry} />
        </instancedMesh>
      ))}
    </group>
  );
}

function AgentPartGeometry({ kind }: { kind: VoxelAgentGeometryKind }) {
  switch (kind) {
    case "head":
      return <icosahedronGeometry args={[0.5, 1]} />;
    case "limb":
      return <cylinderGeometry args={[0.5, 0.5, 1, 6]} />;
    case "torso":
      return <cylinderGeometry args={[0.42, 0.56, 1, 6]} />;
    default:
      return <boxGeometry args={[1, 1, 1]} />;
  }
}

function advanceAgentAnimations(
  runtimes: Map<string, AgentRuntime>,
  poseMap: AgentPoseMap,
  delta: number,
): { changed: boolean; needsNextFrame: boolean } {
  let changed = false;
  let needsNextFrame = false;
  const junctionSpeedScales = resolveVoxelJunctionSpeedScales(
    Array.from(runtimes, ([agentId, runtime]) => runtime.animation
      ? {
          agentId,
          distance: runtime.animation.distance,
          formationId: runtime.animation.formation.id,
          junctions: runtime.animation.junctions,
        }
      : null).filter((state) => state !== null),
  );
  for (const [agentId, runtime] of runtimes) {
    const animation = runtime.animation;
    if (!animation) continue;
    if (animation.skipNextFrame) {
      animation.skipNextFrame = false;
      needsNextFrame = true;
      continue;
    }
    const locomotion = advanceVoxelLocomotion(
      animation.path,
      { distance: animation.distance, speed: animation.speed },
      delta,
      {
        authoritativeDistance: animation.authoritativeDistance,
        maxSpeed: animation.walkingSpeed * (junctionSpeedScales.get(agentId) ?? 1),
      },
    );
    animation.distance = locomotion.distance;
    animation.speed = locomotion.speed;
    const sample = offsetVoxelMotionSample(
      animation.path,
      animation.distance,
      sampleVoxelMotionPathAtDistance(animation.path, animation.distance),
      animation.formation.laneOffset,
      animation.formation.longitudinalOffset,
    );
    runtime.basePosition.set(sample.position.x, sample.position.y, sample.position.z);
    const lookAheadDistance = Math.min(
      animation.path.totalLength,
      animation.distance + calculateVoxelLookAheadDistance(animation.speed),
    );
    const lookAhead = offsetVoxelMotionSample(
      animation.path,
      lookAheadDistance,
      sampleVoxelMotionPathAtDistance(animation.path, lookAheadDistance),
      animation.formation.laneOffset,
      animation.formation.longitudinalOffset,
    );
    const lookDirection = {
      x: lookAhead.position.x - sample.position.x,
      z: lookAhead.position.z - sample.position.z,
    };
    const isArriving = animation.distance >= animation.path.totalLength - Number.EPSILON;
    const targetRotationY = isArriving
      ? animation.arrivalRotationY
      : Math.atan2(
          Math.abs(lookDirection.x) + Math.abs(lookDirection.z) > Number.EPSILON
            ? lookDirection.x
            : sample.tangent.x,
          Math.abs(lookDirection.x) + Math.abs(lookDirection.z) > Number.EPSILON
            ? lookDirection.z
            : sample.tangent.z,
        );
    runtime.rotationY = dampAngle(
      runtime.rotationY,
      targetRotationY,
      isArriving ? 7 : 9,
      delta,
    );
    const gaitPhase = calculateVoxelStridePhase(animation.distance);
    const gaitStrength = calculateVoxelGaitStrength(
      animation.speed,
      animation.walkingSpeed,
    );
    runtime.bodyBob = Math.abs(Math.sin(gaitPhase)) * 0.025 * gaitStrength;
    runtime.gaitSwing = Math.sin(gaitPhase) * 0.24 * gaitStrength;
    runtime.avoidanceWeight = calculateVoxelEndpointBlend(
      animation.distance,
      animation.path.totalLength,
    );
    changed = true;
    if (!isArriving || angleDistance(runtime.rotationY, animation.arrivalRotationY) > 0.015) {
      needsNextFrame = true;
    } else {
      runtime.rotationY = animation.arrivalRotationY;
      runtime.completedMotionId = animation.eventId;
      runtime.animation = null;
      runtime.avoidanceWeight = 0;
      resetAgentGait(runtime);
    }
  }

  const neighbors = Array.from(runtimes, ([id, runtime]) => ({
    id,
    position: {
      x: runtime.basePosition.x,
      y: runtime.basePosition.y,
      z: runtime.basePosition.z,
    },
  }));
  const avoidanceDamping = 1 - Math.exp(-10 * Math.min(delta, 0.1));
  for (const [agentId, runtime] of runtimes) {
    const target = runtime.avoidanceWeight > 0
      ? calculateVoxelAvoidanceOffset(agentId, runtime.basePosition, neighbors)
      : { x: 0, y: 0, z: 0 };
    runtime.avoidanceTarget.set(
      target.x * runtime.avoidanceWeight,
      0,
      target.z * runtime.avoidanceWeight,
    );
    runtime.avoidanceOffset.lerp(runtime.avoidanceTarget, avoidanceDamping);
    if (runtime.avoidanceOffset.lengthSq() < 0.000001) runtime.avoidanceOffset.set(0, 0, 0);
    runtime.position.copy(runtime.basePosition).add(runtime.avoidanceOffset);
    publishAgentPose(poseMap, agentId, runtime.position);
    if (runtime.avoidanceOffset.lengthSq() > 0) {
      changed = true;
      needsNextFrame = true;
    }
  }
  return { changed, needsNextFrame };
}

function getOrCreateRuntime(
  runtimes: Map<string, AgentRuntime>,
  agent: VoxelAgentPlan,
): AgentRuntime {
  const existing = runtimes.get(agent.id);
  if (existing) return existing;
  const runtime: AgentRuntime = {
    animation: null,
    avoidanceOffset: new THREE.Vector3(),
    avoidanceTarget: new THREE.Vector3(),
    avoidanceWeight: 0,
    basePosition: new THREE.Vector3(
      agent.anchor.position.x,
      agent.anchor.position.y,
      agent.anchor.position.z,
    ),
    bodyBob: 0,
    completedMotionId: null,
    gaitSwing: 0,
    position: new THREE.Vector3(
      agent.anchor.position.x,
      agent.anchor.position.y,
      agent.anchor.position.z,
    ),
    rotationY: agent.rotationY,
  };
  runtimes.set(agent.id, runtime);
  return runtime;
}

function synchronizeAgentRuntime(
  runtime: AgentRuntime,
  agent: VoxelAgentPlan,
  motion: VoxelMoveTrail | undefined,
  isPaused: boolean,
  prefersReducedMotion: boolean,
  wasPaused: boolean,
): void {
  if (!motion) {
    runtime.animation = null;
    runtime.avoidanceOffset.set(0, 0, 0);
    runtime.avoidanceWeight = 0;
    runtime.completedMotionId = null;
    resetAgentGait(runtime);
    runtime.position.set(
      agent.anchor.position.x,
      agent.anchor.position.y,
      agent.anchor.position.z,
    );
    runtime.basePosition.copy(runtime.position);
    runtime.rotationY = agent.rotationY;
    return;
  }

  const path = buildVoxelMotionPath(motion.points);
  const finalPoint = path.points.at(-1);
  if (prefersReducedMotion || path.totalLength === 0 || path.points.length < 2) {
    runtime.animation = null;
    runtime.completedMotionId = motion.isActive ? null : motion.id;
    resetAgentGait(runtime);
    const progress = motion.isActive ? clampProgress(motion.initialProgress) : 1;
    setRuntimePosition(runtime, sampleVoxelMotionPath(path, progress));
    runtime.rotationY = agent.rotationY;
    return;
  }

  if (runtime.completedMotionId === motion.id) {
    resetAgentGait(runtime);
    if (finalPoint) {
      runtime.basePosition.set(finalPoint.x, finalPoint.y, finalPoint.z);
      runtime.position.copy(runtime.basePosition);
    }
    runtime.avoidanceOffset.set(0, 0, 0);
    runtime.avoidanceWeight = 0;
    runtime.rotationY = agent.rotationY;
    return;
  }

  const activeAnimation = runtime.animation;
  if (activeAnimation?.eventId === motion.id) {
    const previousProgress = activeAnimation.path.totalLength > 0
      ? activeAnimation.distance / activeAnimation.path.totalLength
      : 0;
    activeAnimation.path = path;
    activeAnimation.distance = Math.min(path.totalLength, previousProgress * path.totalLength);
    activeAnimation.arrivalRotationY = agent.rotationY;
    activeAnimation.formation = motion.formation;
    activeAnimation.junctions = motion.junctions.map((junction) => ({
      distance: findNearestVoxelPathDistance(path, junction.position),
      id: junction.id,
    }));
    activeAnimation.walkingSpeed = resolveVoxelWalkingSpeed(
      motion.formation.size > 1 ? motion.formation.id : agent.id,
      motion.speed,
    );
    const authoritativeProgress = clampProgress(motion.initialProgress);
    activeAnimation.authoritativeDistance = authoritativeProgress * path.totalLength;
    if (wasPaused && !isPaused) activeAnimation.skipNextFrame = true;
    if (isPaused) resetAgentGait(runtime);
    return;
  }

  const initialProgress = clampProgress(motion.initialProgress);
  const initialDistance = initialProgress * path.totalLength;
  setRuntimePosition(
    runtime,
    offsetVoxelMotionSample(
      path,
      initialDistance,
      sampleVoxelMotionPathAtDistance(path, initialDistance),
      motion.formation.laneOffset,
      motion.formation.longitudinalOffset,
    ),
  );
  const walkingSpeed = resolveVoxelWalkingSpeed(
    motion.formation.size > 1 ? motion.formation.id : agent.id,
    motion.speed,
  );
  runtime.animation = {
    arrivalRotationY: agent.rotationY,
    authoritativeDistance: initialDistance,
    distance: initialDistance,
    eventId: motion.id,
    formation: motion.formation,
    junctions: motion.junctions.map((junction) => ({
      distance: findNearestVoxelPathDistance(path, junction.position),
      id: junction.id,
    })),
    path,
    skipNextFrame: wasPaused && !isPaused,
    speed: initialProgress > 0 && initialProgress < 1 ? walkingSpeed * 0.72 : 0,
    walkingSpeed,
  };
}

function updateAgentInstanceMatrices(
  mesh: THREE.InstancedMesh,
  parts: VoxelAgentInstancePart[],
  runtimes: Map<string, AgentRuntime>,
  transforms: { root: THREE.Object3D; part: THREE.Object3D },
): void {
  parts.forEach((part, index) => {
    const runtime = runtimes.get(part.agentId);
    if (!runtime) return;
    transforms.root.position.copy(runtime.position);
    transforms.root.rotation.set(0, runtime.rotationY, 0);
    transforms.root.scale.set(1, 1, 1);
    transforms.root.updateMatrix();
    transforms.part.position.set(
      part.position.x,
      part.position.y + runtime.bodyBob,
      part.position.z,
    );
    transforms.part.rotation.set(
      part.rotation.x + runtime.gaitSwing * part.gaitDirection,
      part.rotation.y,
      part.rotation.z,
    );
    transforms.part.scale.set(part.size.x, part.size.y, part.size.z);
    transforms.part.updateMatrix();
    transforms.part.matrix.premultiply(transforms.root.matrix);
    mesh.setMatrixAt(index, transforms.part.matrix);
  });
  mesh.instanceMatrix.needsUpdate = true;
}

function setRuntimePosition(
  runtime: AgentRuntime,
  sample: ReturnType<typeof sampleVoxelMotionPath>,
): void {
  runtime.basePosition.set(sample.position.x, sample.position.y, sample.position.z);
  runtime.avoidanceOffset.set(0, 0, 0);
  runtime.avoidanceWeight = 0;
  runtime.position.copy(runtime.basePosition);
}

function publishAgentPose(poseMap: AgentPoseMap, agentId: string, position: THREE.Vector3): void {
  const current = poseMap.current.get(agentId);
  if (current) current.copy(position);
  else poseMap.current.set(agentId, position.clone());
}

function resetAgentGait(runtime: AgentRuntime): void {
  runtime.bodyBob = 0;
  runtime.gaitSwing = 0;
}

function dampAngle(current: number, target: number, smoothing: number, delta: number): number {
  const difference = Math.atan2(Math.sin(target - current), Math.cos(target - current));
  return current + difference * (1 - Math.exp(-smoothing * delta));
}

function angleDistance(current: number, target: number): number {
  return Math.abs(Math.atan2(Math.sin(target - current), Math.cos(target - current)));
}

function clampProgress(progress: number | undefined): number {
  return Math.min(1, Math.max(0, progress ?? 0));
}
