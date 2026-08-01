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
  const resources = useMemo(() => buildAgentRenderResources(agents), [agents]);
  const motionByAgentId = useMemo(() => {
    const motions = new Map<string, VoxelMoveTrail>();
    for (const trail of moveTrails) {
      if (trail.actorId && !motions.has(trail.actorId)) motions.set(trail.actorId, trail);
    }
    return motions;
  }, [moveTrails]);

  useEffect(
    () => () => {
      resources.geometry.dispose();
      for (const material of resources.materials.values()) material.dispose();
    },
    [resources],
  );

  return (
    <>
      {agents.map((agent) => (
        <VoxelAgent
          key={agent.id}
          agent={agent}
          motion={motionByAgentId.get(agent.id)}
          geometry={resources.geometry}
          materials={resources.materials}
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
  geometry,
  materials,
  poseMap,
  isPaused,
  prefersReducedMotion,
  onAgentClick,
}: {
  agent: VoxelAgentPlan;
  motion?: VoxelMoveTrail;
  geometry: THREE.BoxGeometry;
  materials: Map<number, THREE.MeshLambertMaterial>;
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
  const statusColor = VOXEL_MATERIAL_COLORS[getAgentMaterial(agent.source.status)];
  const appearance = agent.appearance;
  const heightScale = appearance.heightScale;

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
          position={[0, 0.34 * heightScale, 0]}
          size={[0.22, 0.5 * heightScale, 0.18]}
          geometry={geometry}
          material={getAgentMaterialForColor(materials, appearance.torso)}
        />
        <AgentPart
          position={[0, 0.67 * heightScale, 0]}
          size={[0.2, 0.2, 0.2]}
          geometry={geometry}
          material={getAgentMaterialForColor(materials, appearance.skin)}
        />
        <AgentPart
          position={[0, 0.81 * heightScale, -0.01]}
          size={[0.22, 0.08, 0.22]}
          geometry={geometry}
          material={getAgentMaterialForColor(materials, appearance.hair)}
        />
        <AgentPart
          position={[0, 0.45 * heightScale, 0.1]}
          size={[0.13, 0.08, 0.025]}
          geometry={geometry}
          material={getAgentMaterialForColor(materials, statusColor)}
        />
        <AgentPart
          position={[-0.15, 0.39 * heightScale, 0]}
          size={[0.055, 0.34, 0.06]}
          geometry={geometry}
          material={getAgentMaterialForColor(materials, appearance.skin)}
        />
        <AgentPart
          position={[0.15, 0.39 * heightScale, 0]}
          size={[0.055, 0.34, 0.06]}
          geometry={geometry}
          material={getAgentMaterialForColor(materials, appearance.skin)}
        />
        {appearance.accessory === "backpack" ? (
          <AgentPart
            position={[0, 0.4 * heightScale, -0.12]}
            size={[0.19, 0.3, 0.08]}
            geometry={geometry}
            material={getAgentMaterialForColor(materials, appearance.accent)}
          />
        ) : null}
        {appearance.accessory === "satchel" ? (
          <AgentPart
            position={[0.15, 0.31 * heightScale, -0.02]}
            size={[0.09, 0.16, 0.08]}
            geometry={geometry}
            material={getAgentMaterialForColor(materials, appearance.accent)}
          />
        ) : null}
        <AgentPart
          ref={leftLegRef}
          position={[-0.07, 0.08, 0]}
          size={[0.06, 0.16, 0.06]}
          geometry={geometry}
          material={getAgentMaterialForColor(materials, appearance.trousers)}
        />
        <AgentPart
          ref={rightLegRef}
          position={[0.07, 0.08, 0]}
          size={[0.06, 0.16, 0.06]}
          geometry={geometry}
          material={getAgentMaterialForColor(materials, appearance.trousers)}
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
    geometry: THREE.BoxGeometry;
    material: THREE.MeshLambertMaterial;
  }
>(function AgentPart({ position, size, geometry, material }, ref) {
  return (
    <mesh
      ref={ref}
      position={position}
      scale={size}
      geometry={geometry}
      material={material}
      castShadow
      receiveShadow
      dispose={null}
    />
  );
});

type AgentRenderResources = {
  geometry: THREE.BoxGeometry;
  materials: Map<number, THREE.MeshLambertMaterial>;
};

function buildAgentRenderResources(agents: VoxelAgentPlan[]): AgentRenderResources {
  const colors = new Set<number>();
  for (const agent of agents) {
    const { appearance } = agent;
    colors.add(appearance.torso);
    colors.add(appearance.skin);
    colors.add(appearance.hair);
    colors.add(appearance.accent);
    colors.add(appearance.trousers);
    colors.add(VOXEL_MATERIAL_COLORS[getAgentMaterial(agent.source.status)]);
  }
  return {
    geometry: new THREE.BoxGeometry(1, 1, 1),
    materials: new Map(
      Array.from(colors, (color) => [color, new THREE.MeshLambertMaterial({ color })]),
    ),
  };
}

function getAgentMaterialForColor(
  materials: Map<number, THREE.MeshLambertMaterial>,
  color: number,
): THREE.MeshLambertMaterial {
  const material = materials.get(color);
  if (!material) throw new Error(`Missing shared agent material for color ${color}`);
  return material;
}

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
