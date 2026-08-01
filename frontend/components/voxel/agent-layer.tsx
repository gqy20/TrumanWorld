"use client";

import { type ThreeEvent, useFrame, useThree } from "@react-three/fiber";
import { type MutableRefObject, useEffect, useLayoutEffect, useMemo, useRef } from "react";
import * as THREE from "three";

import { buildVoxelAgentInstanceParts, type VoxelAgentInstancePart } from "./agent-instances";
import {
  advanceVoxelMotionProgress,
  buildVoxelMotionPath,
  calculateVoxelMotionDuration,
  sampleVoxelMotionPath,
  type VoxelMotionPath,
} from "./agent-motion";
import type { VoxelMoveTrail } from "./event-plan";
import type { VoxelAgentPlan } from "./types";

export type AgentPoseMap = MutableRefObject<Map<string, THREE.Vector3>>;

type AgentAnimation = {
  durationMs: number;
  eventId: string;
  path: VoxelMotionPath;
  progress: number;
  skipNextFrame: boolean;
};

type AgentRuntime = {
  animation: AgentAnimation | null;
  bodyBob: number;
  completedMotionId: string | null;
  gaitSwing: number;
  position: THREE.Vector3;
  rotationY: number;
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
  const meshRef = useRef<THREE.InstancedMesh>(null);
  const runtimesRef = useRef<Map<string, AgentRuntime>>(new Map());
  const previousPausedRef = useRef(isPaused);
  const transformRef = useRef({ root: new THREE.Object3D(), part: new THREE.Object3D() });
  const invalidate = useThree((state) => state.invalidate);
  const parts = useMemo(() => buildVoxelAgentInstanceParts(agents), [agents]);
  const motionByAgentId = useMemo(() => {
    const motions = new Map<string, VoxelMoveTrail>();
    for (const trail of moveTrails) {
      if (trail.actorId && !motions.has(trail.actorId)) motions.set(trail.actorId, trail);
    }
    return motions;
  }, [moveTrails]);

  useLayoutEffect(() => {
    const mesh = meshRef.current;
    if (!mesh) return;
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

    mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    parts.forEach((part, index) => mesh.setColorAt(index, new THREE.Color(part.color)));
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
    updateAgentInstanceMatrices(
      mesh,
      parts,
      runtimesRef.current,
      transformRef.current,
    );
    invalidate();
  }, [
    agents,
    invalidate,
    isPaused,
    motionByAgentId,
    parts,
    poseMap,
    prefersReducedMotion,
  ]);

  useEffect(
    () => () => {
      for (const agentId of runtimesRef.current.keys()) poseMap.current.delete(agentId);
    },
    [poseMap],
  );

  useFrame((_state, delta) => {
    const mesh = meshRef.current;
    if (!mesh || isPaused) return;
    const { changed, needsNextFrame } = advanceAgentAnimations(
      runtimesRef.current,
      poseMap,
      delta,
    );
    if (changed) {
      updateAgentInstanceMatrices(
        mesh,
        parts,
        runtimesRef.current,
        transformRef.current,
      );
    }
    if (needsNextFrame) invalidate();
  });

  const handleClick = (event: ThreeEvent<MouseEvent>) => {
    const agentId =
      event.instanceId === undefined ? undefined : parts[event.instanceId]?.agentId;
    if (!agentId) return;
    event.stopPropagation();
    onAgentClick?.(agentId);
  };

  if (parts.length === 0) return null;
  return (
    <instancedMesh
      ref={meshRef}
      args={[undefined, undefined, parts.length]}
      castShadow
      receiveShadow
      frustumCulled={false}
      onClick={handleClick}
    >
      <boxGeometry args={[1, 1, 1]} />
      <meshLambertMaterial color={0xffffff} />
    </instancedMesh>
  );
}

function advanceAgentAnimations(
  runtimes: Map<string, AgentRuntime>,
  poseMap: AgentPoseMap,
  delta: number,
): { changed: boolean; needsNextFrame: boolean } {
  let changed = false;
  let needsNextFrame = false;
  for (const [agentId, runtime] of runtimes) {
    const animation = runtime.animation;
    if (!animation) continue;
    if (animation.skipNextFrame) {
      animation.skipNextFrame = false;
      needsNextFrame = true;
      continue;
    }
    const progress = advanceVoxelMotionProgress(
      animation.progress,
      animation.durationMs,
      delta,
      false,
    );
    animation.progress = progress;
    const sample = sampleVoxelMotionPath(animation.path, progress);
    runtime.position.set(sample.position.x, sample.position.y, sample.position.z);
    runtime.rotationY = dampAngle(
      runtime.rotationY,
      Math.atan2(sample.tangent.x, sample.tangent.z),
      14,
      delta,
    );
    const gaitPhase = progress * animation.path.totalLength * Math.PI * 3.4;
    runtime.bodyBob = Math.abs(Math.sin(gaitPhase)) * 0.025;
    runtime.gaitSwing = Math.sin(gaitPhase) * 0.24;
    publishAgentPose(poseMap, agentId, runtime.position);
    changed = true;
    if (progress < 1) {
      needsNextFrame = true;
    } else {
      runtime.completedMotionId = animation.eventId;
      runtime.animation = null;
      resetAgentGait(runtime);
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
    bodyBob: 0,
    completedMotionId: null,
    gaitSwing: 0,
    position: new THREE.Vector3(
      agent.anchor.position.x,
      Math.max(0, agent.anchor.position.y - 0.04),
      agent.anchor.position.z,
    ),
    rotationY: 0,
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
    runtime.completedMotionId = null;
    resetAgentGait(runtime);
    runtime.position.set(
      agent.anchor.position.x,
      Math.max(0, agent.anchor.position.y - 0.04),
      agent.anchor.position.z,
    );
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
    return;
  }

  if (runtime.completedMotionId === motion.id) {
    resetAgentGait(runtime);
    if (finalPoint) runtime.position.set(finalPoint.x, finalPoint.y, finalPoint.z);
    return;
  }

  const activeAnimation = runtime.animation;
  if (activeAnimation?.eventId === motion.id) {
    activeAnimation.path = path;
    activeAnimation.durationMs = Math.max(1, calculateVoxelMotionDuration(path.totalLength));
    const authoritativeProgress = clampProgress(motion.initialProgress);
    if (authoritativeProgress > activeAnimation.progress) {
      activeAnimation.progress = authoritativeProgress;
      setRuntimePosition(runtime, sampleVoxelMotionPath(path, authoritativeProgress));
    }
    if (wasPaused && !isPaused) activeAnimation.skipNextFrame = true;
    if (isPaused) resetAgentGait(runtime);
    return;
  }

  const initialProgress = clampProgress(motion.initialProgress);
  setRuntimePosition(runtime, sampleVoxelMotionPath(path, initialProgress));
  runtime.animation = {
    durationMs: Math.max(1, calculateVoxelMotionDuration(path.totalLength)),
    eventId: motion.id,
    path,
    progress: initialProgress,
    skipNextFrame: wasPaused && !isPaused,
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
    transforms.part.rotation.set(runtime.gaitSwing * part.gaitDirection, 0, 0);
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
  runtime.position.set(sample.position.x, sample.position.y, sample.position.z);
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

function clampProgress(progress: number | undefined): number {
  return Math.min(1, Math.max(0, progress ?? 0));
}
