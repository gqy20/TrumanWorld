"use client";

import { Canvas, type ThreeEvent, useThree } from "@react-three/fiber";
import { useLayoutEffect, useMemo, useRef } from "react";
import * as THREE from "three";

import { VOXEL_MATERIAL_COLORS } from "./materials";
import type { VoxelWorldRendererProps } from "./renderer-types";
import { buildVoxelScenePlan } from "./scene-plan";
import type {
  VoxelBlock,
  VoxelBounds,
  VoxelHitTarget,
  VoxelMaterialKey,
  VoxelScenePlan,
  VoxelSelectionAnchor,
} from "./types";

type BlockBatch = {
  key: string;
  material: VoxelMaterialKey;
  castShadow: boolean;
  receiveShadow: boolean;
  blocks: VoxelBlock[];
};

export function VoxelCanvas({
  sceneWorld,
  highlightedLocationId,
  highlightedAgentId,
  onAgentClick,
  onLocationClick,
}: VoxelWorldRendererProps) {
  const plan = useMemo(() => buildVoxelScenePlan(sceneWorld), [sceneWorld]);
  const backgroundColor = sceneWorld.stage.palette?.backgroundColor ?? "#eef5e8";

  return (
    <div
      data-testid="voxel-stage-container"
      role="region"
      aria-label="Truman World 三维世界舞台"
      className="relative h-[380px] min-h-[380px] w-full overflow-hidden rounded-2xl border border-emerald-100 bg-[#eef5e8] shadow-xs sm:h-full sm:min-h-[520px] xl:min-h-[560px]"
    >
      <Canvas
        orthographic
        frameloop="demand"
        dpr={[1, 1.75]}
        shadows={{ type: THREE.PCFShadowMap }}
        gl={{ antialias: true, alpha: false, powerPreference: "high-performance" }}
        camera={{ near: 0.1, far: 100, position: [10, 9, 10] }}
        fallback={<StageFallback />}
      >
        <color attach="background" args={[backgroundColor]} />
        <StageScene
          plan={plan}
          highlightedLocationId={highlightedLocationId}
          highlightedAgentId={highlightedAgentId}
          onAgentClick={onAgentClick}
          onLocationClick={onLocationClick}
        />
      </Canvas>
      <p className="sr-only">
        该舞台展示地点、道路和居民当前位置；可切换到导演地图获取文字化地图交互。
      </p>
    </div>
  );
}

function StageFallback() {
  return (
    <div className="flex h-full min-h-[380px] items-center justify-center bg-slate-50 px-6 text-center text-sm text-slate-500 sm:min-h-[420px]">
      当前浏览器无法启动三维舞台，请切换到导演地图。
    </div>
  );
}

function StageScene({
  plan,
  highlightedLocationId,
  highlightedAgentId,
  onAgentClick,
  onLocationClick,
}: {
  plan: VoxelScenePlan;
  highlightedLocationId?: string | null;
  highlightedAgentId?: string | null;
  onAgentClick?: (agentId: string) => void;
  onLocationClick?: (locationId: string) => void;
}) {
  const batches = useMemo(() => buildBlockBatches(plan.blocks), [plan.blocks]);

  return (
    <>
      <CameraRig bounds={plan.bounds} />
      <hemisphereLight args={[0xffffff, 0x9fb18d, 2.2]} />
      <directionalLight
        castShadow
        color={0xffffff}
        intensity={2.4}
        position={[6, 10, 5]}
        shadow-mapSize-width={1024}
        shadow-mapSize-height={1024}
        shadow-camera-near={0.1}
        shadow-camera-far={40}
      />
      {batches.map((batch) => (
        <InstancedBlockBatch
          key={batch.key}
          batch={batch}
          onAgentClick={onAgentClick}
          onLocationClick={onLocationClick}
        />
      ))}
      <SelectionLayer
        locationAnchor={
          highlightedLocationId ? plan.locationAnchors[highlightedLocationId] : undefined
        }
        agentAnchor={highlightedAgentId ? plan.agentAnchors[highlightedAgentId] : undefined}
      />
    </>
  );
}

function CameraRig({ bounds }: { bounds: VoxelBounds }) {
  const getThreeState = useThree((state) => state.get);
  const size = useThree((state) => state.size);
  const invalidate = useThree((state) => state.invalidate);

  useLayoutEffect(() => {
    const camera = getThreeState().camera;
    if (!(camera instanceof THREE.OrthographicCamera)) return;

    const centerX = (bounds.minX + bounds.maxX) / 2;
    const centerZ = (bounds.minZ + bounds.maxZ) / 2;
    const spanX = Math.max(1, bounds.maxX - bounds.minX);
    const spanZ = Math.max(1, bounds.maxZ - bounds.minZ);
    const spanY = Math.max(1, bounds.maxY - bounds.minY);
    const aspect = size.width / Math.max(1, size.height);
    const projectedWidth = (spanX + spanZ) * 0.72;
    const projectedHeight = (spanX + spanZ) * 0.34 + spanY;
    const viewHeight = Math.max(projectedHeight, projectedWidth / Math.max(0.35, aspect)) * 1.12;
    const distance = Math.max(spanX, spanZ, 10) * 0.9;

    camera.left = (-viewHeight * aspect) / 2;
    camera.right = (viewHeight * aspect) / 2;
    camera.top = viewHeight / 2;
    camera.bottom = -viewHeight / 2;
    camera.position.set(centerX + distance, distance * 0.85, centerZ + distance);
    camera.lookAt(centerX, Math.max(0.2, spanY * 0.16), centerZ);
    camera.updateProjectionMatrix();
    camera.updateMatrixWorld();
    invalidate();
  }, [bounds, getThreeState, invalidate, size.height, size.width]);

  return null;
}

function InstancedBlockBatch({
  batch,
  onAgentClick,
  onLocationClick,
}: {
  batch: BlockBatch;
  onAgentClick?: (agentId: string) => void;
  onLocationClick?: (locationId: string) => void;
}) {
  const meshRef = useRef<THREE.InstancedMesh>(null);
  const invalidate = useThree((state) => state.invalidate);

  useLayoutEffect(() => {
    const mesh = meshRef.current;
    if (!mesh) return;
    const transform = new THREE.Object3D();
    batch.blocks.forEach((block, index) => {
      transform.position.set(block.position.x, block.position.y, block.position.z);
      transform.rotation.set(0, block.rotationY, 0);
      transform.scale.set(block.size.x, block.size.y, block.size.z);
      transform.updateMatrix();
      mesh.setMatrixAt(index, transform.matrix);
    });
    mesh.instanceMatrix.needsUpdate = true;
    mesh.computeBoundingSphere();
    invalidate();
  }, [batch.blocks, invalidate]);

  const handleClick = (event: ThreeEvent<MouseEvent>) => {
    const target = resolveHitTarget(batch.blocks, event.instanceId);
    if (!target) return;
    event.stopPropagation();
    if (target.kind === "location") onLocationClick?.(target.id);
    if (target.kind === "agent") onAgentClick?.(target.id);
  };

  return (
    <instancedMesh
      ref={meshRef}
      args={[undefined, undefined, batch.blocks.length]}
      castShadow={batch.castShadow}
      receiveShadow={batch.receiveShadow}
      onClick={handleClick}
    >
      <boxGeometry args={[1, 1, 1]} />
      <meshLambertMaterial color={VOXEL_MATERIAL_COLORS[batch.material]} />
    </instancedMesh>
  );
}

function SelectionLayer({
  locationAnchor,
  agentAnchor,
}: {
  locationAnchor?: VoxelSelectionAnchor;
  agentAnchor?: VoxelSelectionAnchor;
}) {
  return (
    <>
      {locationAnchor ? <SelectionMarker anchor={locationAnchor} opacity={0.48} /> : null}
      {agentAnchor ? <SelectionMarker anchor={agentAnchor} opacity={0.82} /> : null}
    </>
  );
}

function SelectionMarker({
  anchor,
  opacity,
}: {
  anchor: VoxelSelectionAnchor;
  opacity: number;
}) {
  return (
    <mesh
      position={[anchor.position.x, anchor.position.y, anchor.position.z]}
      scale={[anchor.size.x, anchor.size.y, anchor.size.z]}
      receiveShadow
    >
      <boxGeometry args={[1, 1, 1]} />
      <meshBasicMaterial
        color={VOXEL_MATERIAL_COLORS.highlight}
        transparent
        opacity={opacity}
        depthWrite={false}
      />
    </mesh>
  );
}

function buildBlockBatches(blocks: VoxelBlock[]): BlockBatch[] {
  const batches = new Map<string, BlockBatch>();
  for (const block of blocks) {
    const key = `${block.material}:${Number(block.castShadow)}:${Number(block.receiveShadow)}`;
    const batch = batches.get(key) ?? {
      key,
      material: block.material,
      castShadow: block.castShadow,
      receiveShadow: block.receiveShadow,
      blocks: [],
    };
    batch.blocks.push(block);
    batches.set(key, batch);
  }
  return Array.from(batches.values());
}

function resolveHitTarget(
  blocks: VoxelBlock[],
  instanceId: number | undefined,
): VoxelHitTarget | undefined {
  return instanceId === undefined ? undefined : blocks[instanceId]?.hitTarget;
}
