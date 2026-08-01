"use client";

import { type ThreeEvent, useFrame, useThree } from "@react-three/fiber";
import {
  type MutableRefObject,
  forwardRef,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
} from "react";
import * as THREE from "three";

import {
  advanceVoxelMotionProgress,
  buildVoxelMotionPath,
  calculateVoxelMotionDuration,
  sampleVoxelMotionPath,
  type VoxelMotionPath,
} from "./agent-motion";
import type { VoxelMoveTrail } from "./event-plan";
import { VOXEL_MATERIAL_COLORS } from "./materials";
import type { VoxelAgentPlan, VoxelMaterialKey } from "./types";

export type AgentPoseMap = MutableRefObject<Map<string, THREE.Vector3>>;

type AgentAnimation = {
  durationMs: number;
  eventId: string;
  path: VoxelMotionPath;
  progress: number;
  skipNextFrame: boolean;
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
  const motionByAgentId = useMemo(() => {
    const motions = new Map<string, VoxelMoveTrail>();
    for (const trail of moveTrails) {
      if (trail.actorId && !motions.has(trail.actorId)) motions.set(trail.actorId, trail);
    }
    return motions;
  }, [moveTrails]);

  return (
    <>
      {agents.map((agent) => (
        <VoxelAgent
          key={agent.id}
          agent={agent}
          motion={motionByAgentId.get(agent.id)}
          poseMap={poseMap}
          isPaused={isPaused}
          prefersReducedMotion={prefersReducedMotion}
          onAgentClick={onAgentClick}
        />
      ))}
    </>
  );
}

function VoxelAgent({
  agent,
  motion,
  poseMap,
  isPaused,
  prefersReducedMotion,
  onAgentClick,
}: {
  agent: VoxelAgentPlan;
  motion?: VoxelMoveTrail;
  poseMap: AgentPoseMap;
  isPaused: boolean;
  prefersReducedMotion: boolean;
  onAgentClick?: (agentId: string) => void;
}) {
  const rootRef = useRef<THREE.Group>(null);
  const bodyRef = useRef<THREE.Group>(null);
  const leftLegRef = useRef<THREE.Mesh>(null);
  const rightLegRef = useRef<THREE.Mesh>(null);
  const animationRef = useRef<AgentAnimation | null>(null);
  const completedMotionIdRef = useRef<string | null>(null);
  const previousPausedRef = useRef(isPaused);
  const invalidate = useThree((state) => state.invalidate);
  const bodyMaterial = getAgentMaterial(agent.source.status);

  useLayoutEffect(() => {
    const root = rootRef.current;
    if (!root) return;
    const wasPaused = previousPausedRef.current;
    previousPausedRef.current = isPaused;

    if (!motion) {
      animationRef.current = null;
      completedMotionIdRef.current = null;
      resetAgentGait(bodyRef.current, leftLegRef.current, rightLegRef.current);
      root.position.set(
        agent.anchor.position.x,
        Math.max(0, agent.anchor.position.y - 0.04),
        agent.anchor.position.z,
      );
      publishAgentPose(poseMap, agent.id, root.position);
      invalidate();
      return;
    }

    const path = buildVoxelMotionPath(motion.points);
    const finalPoint = path.points.at(-1);
    if (prefersReducedMotion || path.totalLength === 0 || path.points.length < 2) {
      animationRef.current = null;
      completedMotionIdRef.current = motion.isActive ? null : motion.id;
      resetAgentGait(bodyRef.current, leftLegRef.current, rightLegRef.current);
      const staticProgress = motion.isActive
        ? Math.min(1, Math.max(0, motion.initialProgress ?? 0))
        : 1;
      const staticSample = sampleVoxelMotionPath(path, staticProgress);
      root.position.set(
        staticSample.position.x,
        staticSample.position.y,
        staticSample.position.z,
      );
      publishAgentPose(poseMap, agent.id, root.position);
      invalidate();
      return;
    }

    if (completedMotionIdRef.current === motion.id) {
      resetAgentGait(bodyRef.current, leftLegRef.current, rightLegRef.current);
      if (finalPoint) root.position.set(finalPoint.x, finalPoint.y, finalPoint.z);
      publishAgentPose(poseMap, agent.id, root.position);
      invalidate();
      return;
    }

    const activeAnimation = animationRef.current;
    if (activeAnimation?.eventId === motion.id) {
      activeAnimation.path = path;
      activeAnimation.durationMs = calculateVoxelMotionDuration(path.totalLength);
      const authoritativeProgress = Math.min(1, Math.max(0, motion.initialProgress ?? 0));
      if (authoritativeProgress > activeAnimation.progress) {
        activeAnimation.progress = authoritativeProgress;
        const authoritativeSample = sampleVoxelMotionPath(path, authoritativeProgress);
        root.position.set(
          authoritativeSample.position.x,
          authoritativeSample.position.y,
          authoritativeSample.position.z,
        );
        publishAgentPose(poseMap, agent.id, root.position);
      }
      if (wasPaused && !isPaused) activeAnimation.skipNextFrame = true;
      if (isPaused) {
        resetAgentGait(bodyRef.current, leftLegRef.current, rightLegRef.current);
      }
      invalidate();
      return;
    }

    const initialProgress = Math.min(1, Math.max(0, motion.initialProgress ?? 0));
    const initialSample = sampleVoxelMotionPath(path, initialProgress);
    root.position.set(
      initialSample.position.x,
      initialSample.position.y,
      initialSample.position.z,
    );
    publishAgentPose(poseMap, agent.id, root.position);
    animationRef.current = {
      durationMs: Math.max(1, calculateVoxelMotionDuration(path.totalLength)),
      eventId: motion.id,
      path,
      progress: initialProgress,
      skipNextFrame: wasPaused && !isPaused,
    };
    invalidate();
  }, [
    agent.anchor.position.x,
    agent.anchor.position.y,
    agent.anchor.position.z,
    agent.id,
    invalidate,
    isPaused,
    motion,
    poseMap,
    prefersReducedMotion,
  ]);

  useEffect(
    () => () => {
      poseMap.current.delete(agent.id);
    },
    [agent.id, poseMap],
  );

  useFrame((_state, delta) => {
    const root = rootRef.current;
    const body = bodyRef.current;
    const animation = animationRef.current;
    if (!root || !body || !animation) return;
    if (isPaused) return;
    if (animation.skipNextFrame) {
      animation.skipNextFrame = false;
      invalidate();
      return;
    }

    const progress = advanceVoxelMotionProgress(
      animation.progress,
      animation.durationMs,
      delta,
      false,
    );
    animation.progress = progress;
    const sample = sampleVoxelMotionPath(animation.path, progress);
    root.position.set(sample.position.x, sample.position.y, sample.position.z);
    root.rotation.y = dampAngle(
      root.rotation.y,
      Math.atan2(sample.tangent.x, sample.tangent.z),
      14,
      delta,
    );

    const gaitPhase = progress * animation.path.totalLength * Math.PI * 3.4;
    body.position.y = Math.abs(Math.sin(gaitPhase)) * 0.025;
    if (leftLegRef.current) leftLegRef.current.rotation.x = Math.sin(gaitPhase) * 0.24;
    if (rightLegRef.current) rightLegRef.current.rotation.x = -Math.sin(gaitPhase) * 0.24;
    publishAgentPose(poseMap, agent.id, root.position);

    if (progress < 1) {
      invalidate();
      return;
    }

    completedMotionIdRef.current = animation.eventId;
    animationRef.current = null;
    resetAgentGait(body, leftLegRef.current, rightLegRef.current);
  });

  const handleClick = (event: ThreeEvent<MouseEvent>) => {
    event.stopPropagation();
    onAgentClick?.(agent.id);
  };

  return (
    <group ref={rootRef} onClick={handleClick}>
      <group ref={bodyRef}>
        <AgentPart
          position={[0, 0.34, 0]}
          size={[0.22, 0.5, 0.18]}
          material={bodyMaterial}
        />
        <AgentPart position={[0, 0.68, 0]} size={[0.2, 0.2, 0.2]} material="skin" />
        <AgentPart position={[0, 0.82, -0.01]} size={[0.22, 0.08, 0.22]} material="hair" />
        <AgentPart
          ref={leftLegRef}
          position={[-0.07, 0.08, 0]}
          size={[0.06, 0.16, 0.06]}
          material="trouser"
        />
        <AgentPart
          ref={rightLegRef}
          position={[0.07, 0.08, 0]}
          size={[0.06, 0.16, 0.06]}
          material="trouser"
        />
      </group>
    </group>
  );
}

const AgentPart = forwardRef<
  THREE.Mesh,
  {
    position: [number, number, number];
    size: [number, number, number];
    material: VoxelMaterialKey;
  }
>(function AgentPart({ position, size, material }, ref) {
  return (
    <mesh ref={ref} position={position} scale={size} castShadow receiveShadow>
      <boxGeometry args={[1, 1, 1]} />
      <meshLambertMaterial color={VOXEL_MATERIAL_COLORS[material]} />
    </mesh>
  );
});

function publishAgentPose(poseMap: AgentPoseMap, agentId: string, position: THREE.Vector3): void {
  const current = poseMap.current.get(agentId);
  if (current) current.copy(position);
  else poseMap.current.set(agentId, position.clone());
}

function resetAgentGait(
  body: THREE.Group | null,
  leftLeg: THREE.Mesh | null,
  rightLeg: THREE.Mesh | null,
): void {
  if (body) body.position.y = 0;
  if (leftLeg) leftLeg.rotation.x = 0;
  if (rightLeg) rightLeg.rotation.x = 0;
}

function dampAngle(current: number, target: number, smoothing: number, delta: number): number {
  const difference = Math.atan2(Math.sin(target - current), Math.cos(target - current));
  return current + difference * (1 - Math.exp(-smoothing * delta));
}

function getAgentMaterial(status: VoxelAgentPlan["source"]["status"]): VoxelMaterialKey {
  switch (status) {
    case "moving":
      return "agentMoving";
    case "talking":
      return "agentTalking";
    case "working":
      return "agentWorking";
    case "resting":
      return "agentResting";
    default:
      return "agent";
  }
}
