"use client";

import { Canvas, type ThreeEvent, useFrame, useThree } from "@react-three/fiber";
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";

import { AgentLayer, type AgentPoseMap } from "./agent-layer";
import {
  calculateVoxelCameraFrame,
  calculateVoxelCameraZoom,
  easeOutQuint,
  type VoxelCameraFocusRequest,
  type VoxelCameraSubject,
} from "./camera-controller";
import {
  buildVoxelMotionPath,
  offsetVoxelMotionSample,
  sampleVoxelMotionPathAtDistance,
} from "./agent-motion";
import {
  buildVoxelEventPlan,
  type VoxelEventBubble,
  type VoxelEventPlan,
  type VoxelMoveTrail,
} from "./event-plan";
import {
  getVoxelMaterialClass,
  VOXEL_MATERIAL_CLASS_SPECS,
  VOXEL_MATERIAL_COLORS,
  VOXEL_MATERIAL_SPECS,
  type VoxelMaterialClass,
} from "./materials";
import {
  sampleVoxelRendererMetrics,
  writeVoxelRendererMetrics,
  type VoxelRendererMetrics,
} from "./renderer-metrics";
import type { VoxelWorldRendererProps } from "./renderer-types";
import { buildVoxelScenePlan } from "./scene-plan";
import type {
  VoxelBlock,
  VoxelAssetPlacement,
  VoxelBounds,
  VoxelHitTarget,
  VoxelGeometryKind,
  VoxelScenePlan,
  VoxelSelectionAnchor,
  VoxelVector3,
} from "./types";
import { useActiveVoxelStageEvents } from "./use-stage-events";
import { resolveWorldLightingProfile, type WorldLightingProfile } from "./visual-system";

type BlockBatch = {
  key: string;
  materialClass: VoxelMaterialClass;
  geometry: VoxelGeometryKind;
  castShadow: boolean;
  receiveShadow: boolean;
  blocks: VoxelBlock[];
};

type ResolvedCameraFocus = VoxelCameraFocusRequest & {
  anchor: VoxelSelectionAnchor;
};

type CameraPose = {
  position: THREE.Vector3;
  target: THREE.Vector3;
  zoom: number;
};

type CameraAnimation = {
  durationMs: number;
  from: CameraPose;
  startedAt: number;
  to: CameraPose;
};

type ProjectedBubble = {
  id: string;
  visible: boolean;
  x: number;
  y: number;
};

const SHARED_BLOCK_GEOMETRIES: Record<VoxelGeometryKind, THREE.BufferGeometry> = {
  box: new THREE.BoxGeometry(1, 1, 1),
  cone: new THREE.ConeGeometry(0.5, 1, 4),
  cylinder: new THREE.CylinderGeometry(0.5, 0.5, 1, 12),
  icosphere: new THREE.IcosahedronGeometry(0.5, 1),
};

const WORLD_ASSET_CACHE = new Map<string, Promise<THREE.Object3D>>();

export function VoxelCanvas({
  sceneWorld,
  highlightedLocationId,
  highlightedAgentId,
  cameraFocusRequest,
  onAgentClick,
  onLocationClick,
}: VoxelWorldRendererProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const plan = useMemo(() => buildVoxelScenePlan(sceneWorld), [sceneWorld]);
  const activeStageEvents = useActiveVoxelStageEvents(sceneWorld);
  const movementTrails = useMemo(() => {
    const seen = new Set<string>();
    return [...sceneWorld.activeMovements, ...activeStageEvents.moveTrails].filter((trail) => {
      if (seen.has(trail.id)) return false;
      seen.add(trail.id);
      return true;
    });
  }, [activeStageEvents.moveTrails, sceneWorld.activeMovements]);
  const eventPlan = useMemo(
    () =>
      buildVoxelEventPlan(
        activeStageEvents.bubbles,
        movementTrails,
        plan,
      ),
    [activeStageEvents.bubbles, movementTrails, plan],
  );
  const lightingProfile = useMemo(
    () => resolveWorldLightingProfile(sceneWorld.ambience.timeOfDay),
    [sceneWorld.ambience.timeOfDay],
  );
  const [cameraResetRevision, setCameraResetRevision] = useState(0);
  const [projectedBubbles, setProjectedBubbles] = useState<ProjectedBubble[]>([]);
  const [showStageEvents, setShowStageEvents] = useState(true);
  const prefersReducedMotion = usePrefersReducedMotion();
  const stageEventCount = eventPlan.bubbles.length + eventPlan.moveTrails.length;
  const publishRendererMetrics = useCallback((metrics: VoxelRendererMetrics) => {
    if (containerRef.current) writeVoxelRendererMetrics(containerRef.current, metrics);
  }, []);

  return (
    <div
      ref={containerRef}
      data-testid="voxel-stage-container"
      data-voxel-renderer="webgl"
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
        style={{ cursor: "grab", touchAction: "pan-y" }}
        fallback={<StageFallback />}
      >
        <color attach="background" args={[lightingProfile.background]} />
        <fog attach="fog" args={[lightingProfile.fog, 24, 52]} />
        <StageScene
          plan={plan}
          lightingProfile={lightingProfile}
          highlightedLocationId={highlightedLocationId}
          highlightedAgentId={highlightedAgentId}
          cameraFocusRequest={cameraFocusRequest}
          cameraResetRevision={cameraResetRevision}
          eventPlan={eventPlan}
          showStageEvents={showStageEvents}
          isSimulationPaused={!sceneWorld.isRunning}
          prefersReducedMotion={prefersReducedMotion}
          onBubbleProjectionChange={setProjectedBubbles}
          onAgentClick={onAgentClick}
          onLocationClick={onLocationClick}
        />
        <RendererDiagnostics onSample={publishRendererMetrics} />
      </Canvas>
      <StageEventOverlay
        bubbles={showStageEvents ? eventPlan.bubbles : []}
        projectedBubbles={projectedBubbles}
      />
      {stageEventCount > 0 ? (
        <button
          type="button"
          aria-pressed={showStageEvents}
          aria-label={showStageEvents ? "隐藏舞台事件" : "显示舞台事件"}
          title={showStageEvents ? "隐藏舞台事件" : "显示舞台事件"}
          onClick={() => setShowStageEvents((current) => !current)}
          className="absolute bottom-3 left-3 z-20 inline-flex h-9 items-center gap-2 rounded-xl bg-white/95 px-2.5 text-xs font-medium text-slate-600 shadow-[0_2px_8px_rgba(15,23,42,0.12)] transition-colors hover:bg-white hover:text-slate-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white sm:px-3"
        >
          <StageEventsIcon />
          <span className="hidden sm:inline">{showStageEvents ? "隐藏事件" : "显示事件"}</span>
          <span className="min-w-4 rounded-full bg-slate-100 px-1 text-[10px] tabular-nums text-slate-500">
            {stageEventCount}
          </span>
        </button>
      ) : null}
      <button
        type="button"
        data-testid="voxel-camera-reset"
        onClick={() => setCameraResetRevision((revision) => revision + 1)}
        aria-label="重置镜头"
        title="重置镜头；桌面端可滚轮缩放、拖拽平移"
        className="absolute right-3 bottom-3 z-10 inline-flex h-9 items-center gap-2 rounded-xl bg-white/95 px-2.5 text-xs font-medium text-slate-600 shadow-[0_2px_8px_rgba(15,23,42,0.12)] transition-colors hover:bg-white hover:text-slate-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white sm:px-3"
      >
        <ResetCameraIcon />
        <span className="hidden sm:inline">重置镜头</span>
      </button>
      <p className="sr-only">
        该舞台展示地点、道路和居民当前位置。桌面端可滚轮缩放、拖拽平移，也可切换到导演地图获取文字化地图交互。
      </p>
    </div>
  );
}

function RendererDiagnostics({
  onSample,
}: {
  onSample: (metrics: VoxelRendererMetrics) => void;
}) {
  const gl = useThree((state) => state.gl);

  useEffect(() => {
    let previousFrame = gl.info.render.frame;
    let previousSampleTime = performance.now();
    const sample = () => {
      const sampleTime = performance.now();
      onSample(
        sampleVoxelRendererMetrics(
          previousFrame,
          sampleTime - previousSampleTime,
          gl.info.render,
          gl.info.memory,
        ),
      );
      previousFrame = gl.info.render.frame;
      previousSampleTime = sampleTime;
    };
    const intervalId = window.setInterval(sample, 1000);
    sample();
    return () => window.clearInterval(intervalId);
  }, [gl, onSample]);

  return null;
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
  lightingProfile,
  highlightedLocationId,
  highlightedAgentId,
  cameraFocusRequest,
  cameraResetRevision,
  eventPlan,
  showStageEvents,
  isSimulationPaused,
  prefersReducedMotion,
  onBubbleProjectionChange,
  onAgentClick,
  onLocationClick,
}: {
  plan: VoxelScenePlan;
  lightingProfile: WorldLightingProfile;
  highlightedLocationId?: string | null;
  highlightedAgentId?: string | null;
  cameraFocusRequest?: VoxelCameraFocusRequest | null;
  cameraResetRevision: number;
  eventPlan: VoxelEventPlan;
  showStageEvents: boolean;
  isSimulationPaused: boolean;
  prefersReducedMotion: boolean;
  onBubbleProjectionChange: (bubbles: ProjectedBubble[]) => void;
  onAgentClick?: (agentId: string) => void;
  onLocationClick?: (locationId: string) => void;
}) {
  const batches = useMemo(() => buildBlockBatches(plan.blocks), [plan.blocks]);
  const cameraSubjects = useMemo<VoxelCameraSubject[]>(
    () => [
      ...plan.blocks.filter((block) => block.layer === "core"),
      ...plan.assets.flatMap((asset) => asset.fallbackBlocks),
    ].map(({ position, rotationY, size }) => ({ position, rotationY, size })),
    [plan.assets, plan.blocks],
  );
  const agentPosesRef = useRef<Map<string, THREE.Vector3>>(new Map());
  const resolvedCameraFocus = useMemo<ResolvedCameraFocus | null>(() => {
    if (!cameraFocusRequest) return null;
    const anchor =
      cameraFocusRequest.kind === "agent"
        ? plan.agentAnchors[cameraFocusRequest.id]
        : plan.locationAnchors[cameraFocusRequest.id];
    return anchor ? { ...cameraFocusRequest, anchor } : null;
  }, [cameraFocusRequest, plan.agentAnchors, plan.locationAnchors]);

  return (
    <>
      <RendererConfiguration exposure={lightingProfile.exposure} />
      <CameraRig
        bounds={plan.focusBounds}
        subjects={cameraSubjects}
        focusRequest={resolvedCameraFocus}
        resetRevision={cameraResetRevision}
        agentPosesRef={agentPosesRef}
      />
      <hemisphereLight
        args={[
          lightingProfile.hemisphereSky,
          lightingProfile.hemisphereGround,
          lightingProfile.hemisphereIntensity,
        ]}
      />
      <directionalLight
        castShadow
        color={lightingProfile.sun}
        intensity={lightingProfile.sunIntensity}
        position={lightingProfile.sunPosition}
        shadow-mapSize-width={2048}
        shadow-mapSize-height={2048}
        shadow-camera-near={0.1}
        shadow-camera-far={40}
        shadow-camera-left={-12}
        shadow-camera-right={12}
        shadow-camera-top={12}
        shadow-camera-bottom={-12}
        shadow-bias={-0.00015}
        shadow-normalBias={0.015}
        shadow-radius={2.25}
      />
      <WorldAssetLayer
        placements={plan.assets}
        windowEmissiveIntensity={lightingProfile.windowEmissiveIntensity}
        onLocationClick={onLocationClick}
      />
      {batches.map((batch) => (
        <InstancedBlockBatch
          key={batch.key}
          batch={batch}
          onAgentClick={onAgentClick}
          onLocationClick={onLocationClick}
        />
      ))}
      <AgentLayer
        agents={plan.agents}
        moveTrails={eventPlan.moveTrails}
        poseMap={agentPosesRef}
        isPaused={isSimulationPaused}
        prefersReducedMotion={prefersReducedMotion}
        onAgentClick={onAgentClick}
      />
      <MoveTrailLayer trails={showStageEvents ? eventPlan.moveTrails : []} />
      <BubbleProjectionBridge
        bubbles={showStageEvents ? eventPlan.bubbles : []}
        agentPosesRef={agentPosesRef}
        onProjectionChange={onBubbleProjectionChange}
      />
      <SelectionLayer
        locationAnchor={
          highlightedLocationId ? plan.locationAnchors[highlightedLocationId] : undefined
        }
        agentAnchor={highlightedAgentId ? plan.agentAnchors[highlightedAgentId] : undefined}
        agentId={highlightedAgentId}
        agentPosesRef={agentPosesRef}
      />
    </>
  );
}

function WorldAssetLayer({
  placements,
  windowEmissiveIntensity,
  onLocationClick,
}: {
  placements: VoxelAssetPlacement[];
  windowEmissiveIntensity: number;
  onLocationClick?: (locationId: string) => void;
}) {
  const batches = useMemo(() => {
    const grouped = new Map<string, VoxelAssetPlacement[]>();
    for (const placement of placements) {
      const batch = grouped.get(placement.assetId) ?? [];
      batch.push(placement);
      grouped.set(placement.assetId, batch);
    }
    return Array.from(grouped.entries());
  }, [placements]);
  return (
    <>
      {batches.map(([assetId, assetPlacements]) => (
        <WorldAssetBatch
          key={assetId}
          placements={assetPlacements}
          windowEmissiveIntensity={windowEmissiveIntensity}
          onLocationClick={onLocationClick}
        />
      ))}
    </>
  );
}

type LoadedAssetMesh = {
  geometry: THREE.BufferGeometry;
  localMatrix: THREE.Matrix4;
  material: THREE.Material | THREE.Material[];
  name: string;
};

function WorldAssetBatch({
  placements,
  windowEmissiveIntensity,
  onLocationClick,
}: {
  placements: VoxelAssetPlacement[];
  windowEmissiveIntensity: number;
  onLocationClick?: (locationId: string) => void;
}) {
  const [assetMeshes, setAssetMeshes] = useState<LoadedAssetMesh[] | null>(null);
  const invalidate = useThree((state) => state.invalidate);
  const uri = placements[0]?.uri;

  useEffect(() => {
    if (!uri) return;
    let isActive = true;
    loadWorldAsset(uri)
      .then((source) => {
        if (!isActive) return;
        setAssetMeshes(collectAssetMeshes(source));
        invalidate();
      })
      .catch(() => {
        if (!isActive) return;
        setAssetMeshes(null);
        invalidate();
      });
    return () => {
      isActive = false;
    };
  }, [invalidate, uri]);

  if (!assetMeshes || assetMeshes.length === 0) {
    return (
      <WorldAssetFallback
        blocks={placements.flatMap((placement) => placement.fallbackBlocks)}
        onLocationClick={onLocationClick}
      />
    );
  }

  return (
    <>
      {assetMeshes.map((assetMesh) => (
        <WorldAssetMeshBatch
          key={assetMesh.name}
          assetMesh={assetMesh}
          placements={placements}
          windowEmissiveIntensity={windowEmissiveIntensity}
          onLocationClick={onLocationClick}
        />
      ))}
    </>
  );
}

function WorldAssetMeshBatch({
  assetMesh,
  placements,
  windowEmissiveIntensity,
  onLocationClick,
}: {
  assetMesh: LoadedAssetMesh;
  placements: VoxelAssetPlacement[];
  windowEmissiveIntensity: number;
  onLocationClick?: (locationId: string) => void;
}) {
  const meshRef = useRef<THREE.InstancedMesh>(null);
  const invalidate = useThree((state) => state.invalidate);
  const isWindowGlow = assetMesh.name.endsWith("WindowGlow");
  const renderedMaterial = useMemo(() => {
    if (!isWindowGlow) return assetMesh.material;
    const withLighting = (material: THREE.Material) => {
      const localMaterial = material.clone();
      if (localMaterial instanceof THREE.MeshStandardMaterial) {
        localMaterial.emissiveIntensity = windowEmissiveIntensity;
      }
      return localMaterial;
    };
    return Array.isArray(assetMesh.material)
      ? assetMesh.material.map(withLighting)
      : withLighting(assetMesh.material);
  }, [assetMesh.material, isWindowGlow, windowEmissiveIntensity]);

  useEffect(() => {
    invalidate();
    return () => {
      if (!isWindowGlow) return;
      const materials = Array.isArray(renderedMaterial) ? renderedMaterial : [renderedMaterial];
      for (const material of materials) material.dispose();
    };
  }, [invalidate, isWindowGlow, renderedMaterial]);

  useLayoutEffect(() => {
    const mesh = meshRef.current;
    if (!mesh) return;
    const transform = new THREE.Object3D();
    placements.forEach((placement, index) => {
      transform.position.set(placement.position.x, placement.position.y, placement.position.z);
      transform.rotation.set(0, placement.rotationY, 0);
      transform.scale.set(placement.scale.x, placement.scale.y, placement.scale.z);
      transform.updateMatrix();
      transform.matrix.multiply(assetMesh.localMatrix);
      mesh.setMatrixAt(index, transform.matrix);
    });
    mesh.instanceMatrix.needsUpdate = true;
    mesh.computeBoundingSphere();
    invalidate();
  }, [assetMesh.localMatrix, invalidate, placements]);

  return (
    <instancedMesh
      ref={meshRef}
      args={[assetMesh.geometry, renderedMaterial, placements.length]}
      castShadow={!isWindowGlow}
      receiveShadow={!isWindowGlow}
      onClick={(event: ThreeEvent<MouseEvent>) => {
        const placement =
          event.instanceId === undefined ? undefined : placements[event.instanceId];
        if (!placement) return;
        event.stopPropagation();
        onLocationClick?.(placement.locationId);
      }}
    />
  );
}

function collectAssetMeshes(source: THREE.Object3D): LoadedAssetMesh[] {
  source.updateMatrixWorld(true);
  const meshes: LoadedAssetMesh[] = [];
  source.traverse((child) => {
    if (!(child instanceof THREE.Mesh)) return;
    meshes.push({
      geometry: child.geometry,
      localMatrix: child.matrixWorld.clone(),
      material: child.material,
      name: child.name || child.uuid,
    });
  });
  return meshes;
}

function WorldAssetFallback({
  blocks,
  onLocationClick,
}: {
  blocks: VoxelBlock[];
  onLocationClick?: (locationId: string) => void;
}) {
  const batches = useMemo(() => buildBlockBatches(blocks), [blocks]);
  return (
    <>
      {batches.map((batch) => (
        <InstancedBlockBatch
          key={`fallback:${batch.key}`}
          batch={batch}
          onLocationClick={onLocationClick}
        />
      ))}
    </>
  );
}

function loadWorldAsset(uri: string): Promise<THREE.Object3D> {
  const cached = WORLD_ASSET_CACHE.get(uri);
  if (cached) return cached;
  const pending = new Promise<THREE.Object3D>((resolve, reject) => {
    new GLTFLoader().load(uri, (gltf) => resolve(gltf.scene), undefined, reject);
  }).catch((error) => {
    WORLD_ASSET_CACHE.delete(uri);
    throw error;
  });
  WORLD_ASSET_CACHE.set(uri, pending);
  return pending;
}

function RendererConfiguration({ exposure }: { exposure: number }) {
  const gl = useThree((state) => state.gl);
  const rendererRef = useRef(gl);
  const invalidate = useThree((state) => state.invalidate);

  useEffect(() => {
    const renderer = rendererRef.current;
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.AgXToneMapping;
    renderer.toneMappingExposure = exposure;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFShadowMap;
    invalidate();
  }, [exposure, invalidate]);

  return null;
}

function StageEventOverlay({
  bubbles,
  projectedBubbles,
}: {
  bubbles: VoxelEventBubble[];
  projectedBubbles: ProjectedBubble[];
}) {
  const projectionById = new Map(projectedBubbles.map((bubble) => [bubble.id, bubble]));
  const visibleBubbles = resolveBubbleCollisions(
    bubbles.flatMap((bubble) => {
      const projection = projectionById.get(bubble.id);
      return projection?.visible ? [{ bubble, projection }] : [];
    }),
  );

  return (
    <div
      className="pointer-events-none absolute inset-0 z-10 overflow-hidden"
      aria-live="polite"
      aria-atomic="false"
    >
      {visibleBubbles.map(({ bubble, projection }) => (
        <div
          key={bubble.id}
          data-testid={`voxel-event-bubble-${bubble.id}`}
          className={`absolute -translate-x-1/2 -translate-y-full px-2 pb-3 ${
            bubble.recencyIndex > 0 ? "hidden sm:block" : ""
          }`}
          style={{ left: projection.x, top: projection.y }}
        >
          <div className="voxel-stage-event-bubble relative min-w-36 max-w-[210px] rounded-xl bg-white px-3 py-2 text-left shadow-[0_2px_8px_rgba(15,23,42,0.18)]">
            <p className="truncate text-[10px] font-semibold text-moss">{bubble.speakerName}</p>
            <p className="mt-0.5 line-clamp-2 text-xs leading-[1.4] text-slate-700">
              {bubble.text}
            </p>
            <span
              aria-hidden="true"
              className="absolute -bottom-1.5 left-1/2 h-3 w-3 -translate-x-1/2 rotate-45 bg-white"
            />
          </div>
        </div>
      ))}
    </div>
  );
}

function BubbleProjectionBridge({
  bubbles,
  agentPosesRef,
  onProjectionChange,
}: {
  bubbles: VoxelEventBubble[];
  agentPosesRef: AgentPoseMap;
  onProjectionChange: (bubbles: ProjectedBubble[]) => void;
}) {
  const invalidate = useThree((state) => state.invalidate);
  const lastProjectionRef = useRef("");

  useEffect(() => {
    if (bubbles.length === 0) {
      lastProjectionRef.current = "";
      onProjectionChange([]);
    }
    invalidate();
  }, [bubbles, invalidate, onProjectionChange]);

  useFrame(({ camera, size }) => {
    const horizontalMargin = Math.min(106, size.width * 0.25);
    const minimumBubbleY = size.width < 640 ? 160 : 118;
    const projected = bubbles.map((bubble) => {
      const liveAgentPosition = bubble.speakerAgentId
        ? agentPosesRef.current.get(bubble.speakerAgentId)
        : undefined;
      const point = new THREE.Vector3(
        liveAgentPosition?.x ?? bubble.position.x,
        bubble.position.y,
        liveAgentPosition?.z ?? bubble.position.z,
      ).project(camera);
      const rawX = (point.x * 0.5 + 0.5) * size.width;
      const rawY = (-point.y * 0.5 + 0.5) * size.height;
      return {
        id: bubble.id,
        visible: point.z >= -1 && point.z <= 1,
        x: Math.round(Math.min(size.width - horizontalMargin, Math.max(horizontalMargin, rawX))),
        y: Math.round(Math.min(size.height - 28, Math.max(minimumBubbleY, rawY))),
      };
    });
    const signature = projected
      .map((bubble) => `${bubble.id}:${Number(bubble.visible)}:${bubble.x}:${bubble.y}`)
      .join("|");
    if (signature === lastProjectionRef.current) return;
    lastProjectionRef.current = signature;
    onProjectionChange(projected);
  });

  return null;
}

function MoveTrailLayer({ trails }: { trails: VoxelMoveTrail[] }) {
  return (
    <>
      {trails.map((trail) => (
        <MoveTrailMarkers key={trail.id} trail={trail} />
      ))}
    </>
  );
}

function MoveTrailMarkers({ trail }: { trail: VoxelMoveTrail }) {
  const meshRef = useRef<THREE.InstancedMesh>(null);
  const invalidate = useThree((state) => state.invalidate);
  const markerPoints = useMemo(() => {
    const path = buildVoxelMotionPath(trail.points);
    const formedPath = path.cumulativeLengths.map((distance) =>
      offsetVoxelMotionSample(
        path,
        distance,
        sampleVoxelMotionPathAtDistance(path, distance),
        trail.formation.laneOffset,
        trail.formation.longitudinalOffset,
      ).position,
    );
    return interpolateTrailPoints(formedPath);
  }, [trail.formation.laneOffset, trail.formation.longitudinalOffset, trail.points]);

  useLayoutEffect(() => {
    const mesh = meshRef.current;
    if (!mesh) return;
    const transform = new THREE.Object3D();
    const progressDenominator = Math.max(1, markerPoints.length - 1);
    markerPoints.forEach((point, index) => {
      const progress = index / progressDenominator;
      const markerSize = 0.14 + progress * 0.14;
      transform.position.set(point.x, point.y + 0.19, point.z);
      transform.rotation.set(0, Math.PI / 4, 0);
      transform.scale.set(markerSize, 0.035, markerSize);
      transform.updateMatrix();
      mesh.setMatrixAt(index, transform.matrix);
    });
    mesh.instanceMatrix.needsUpdate = true;
    mesh.computeBoundingSphere();
    invalidate();
  }, [invalidate, markerPoints]);

  return (
    <instancedMesh
      ref={meshRef}
      args={[undefined, undefined, markerPoints.length]}
      frustumCulled={false}
      renderOrder={3}
    >
      <boxGeometry args={[1, 1, 1]} />
      <meshBasicMaterial
        color={0xd86f45}
        transparent
        opacity={0.82}
        depthWrite={false}
        toneMapped={false}
      />
    </instancedMesh>
  );
}

function BatchGeometry({ kind }: { kind: VoxelGeometryKind }) {
  return <primitive attach="geometry" object={SHARED_BLOCK_GEOMETRIES[kind]} />;
}

function resolveBubbleCollisions(
  items: Array<{ bubble: VoxelEventBubble; projection: ProjectedBubble }>,
): Array<{ bubble: VoxelEventBubble; projection: ProjectedBubble }> {
  const resolved: Array<{ bubble: VoxelEventBubble; projection: ProjectedBubble }> = [];
  for (const item of items) {
    const projection = { ...item.projection };
    const collision = resolved.find(
      (candidate) =>
        Math.abs(candidate.projection.x - projection.x) < 150 &&
        Math.abs(candidate.projection.y - projection.y) < 68,
    );
    if (collision) {
      projection.y =
        collision.projection.y >= 176
          ? collision.projection.y - 78
          : collision.projection.y + 78;
    }
    resolved.push({ bubble: item.bubble, projection });
  }
  return resolved;
}

function interpolateTrailPoints(points: VoxelVector3[]): VoxelVector3[] {
  return points.flatMap((point, index) => {
    const nextPoint = points[index + 1];
    if (!nextPoint) return [point];
    return [
      point,
      {
        x: (point.x + nextPoint.x) / 2,
        y: (point.y + nextPoint.y) / 2,
        z: (point.z + nextPoint.z) / 2,
      },
    ];
  });
}

function CameraRig({
  bounds,
  subjects,
  focusRequest,
  resetRevision,
  agentPosesRef,
}: {
  bounds: VoxelBounds;
  subjects: VoxelCameraSubject[];
  focusRequest: ResolvedCameraFocus | null;
  resetRevision: number;
  agentPosesRef: AgentPoseMap;
}) {
  const getThreeState = useThree((state) => state.get);
  const size = useThree((state) => state.size);
  const invalidate = useThree((state) => state.invalidate);
  const prefersReducedMotion = usePrefersReducedMotion();
  const lookTargetRef = useRef(new THREE.Vector3());
  const basePoseRef = useRef<CameraPose | null>(null);
  const animationRef = useRef<CameraAnimation | null>(null);
  const lastResetRevisionRef = useRef(resetRevision);
  const { maxX, maxY, maxZ, minX, minY, minZ } = bounds;
  const { height: viewportHeight, width: viewportWidth } = size;
  const frame = useMemo(
    () =>
      calculateVoxelCameraFrame(
        { maxX, maxY, maxZ, minX, minY, minZ },
        { height: viewportHeight, width: viewportWidth },
        subjects,
      ),
    [maxX, maxY, maxZ, minX, minY, minZ, subjects, viewportHeight, viewportWidth],
  );
  const focusAnchorX = focusRequest?.anchor.position.x;
  const focusAnchorZ = focusRequest?.anchor.position.z;
  const focusId = focusRequest?.id;
  const focusKind = focusRequest?.kind;
  const focusRevision = focusRequest?.revision;

  const applyPose = useCallback(
    (pose: CameraPose) => {
      const camera = getThreeState().camera;
      if (!(camera instanceof THREE.OrthographicCamera)) return;
      camera.position.copy(pose.position);
      camera.zoom = pose.zoom;
      lookTargetRef.current.copy(pose.target);
      camera.lookAt(lookTargetRef.current);
      camera.updateProjectionMatrix();
      camera.updateMatrixWorld();
      invalidate();
    },
    [getThreeState, invalidate],
  );

  const animateTo = useCallback(
    (pose: CameraPose) => {
      const camera = getThreeState().camera;
      if (!(camera instanceof THREE.OrthographicCamera)) return;
      const durationMs = prefersReducedMotion ? 0 : 220;
      if (durationMs === 0) {
        animationRef.current = null;
        applyPose(pose);
        return;
      }
      animationRef.current = {
        durationMs,
        from: {
          position: camera.position.clone(),
          target: lookTargetRef.current.clone(),
          zoom: camera.zoom,
        },
        startedAt: performance.now(),
        to: pose,
      };
      invalidate();
    },
    [applyPose, getThreeState, invalidate, prefersReducedMotion],
  );

  useLayoutEffect(() => {
    const camera = getThreeState().camera;
    if (!(camera instanceof THREE.OrthographicCamera)) return;
    camera.left = (-frame.viewHeight * frame.aspect) / 2;
    camera.right = (frame.viewHeight * frame.aspect) / 2;
    camera.top = frame.viewHeight / 2;
    camera.bottom = -frame.viewHeight / 2;
    const pose = {
      position: toThreeVector(frame.position),
      target: toThreeVector(frame.target),
      zoom: 1,
    };
    basePoseRef.current = cloneCameraPose(pose);
    animationRef.current = null;
    applyPose(pose);
  }, [applyPose, frame, getThreeState]);

  useEffect(() => {
    if (
      focusAnchorX === undefined ||
      focusAnchorZ === undefined ||
      !focusKind ||
      !basePoseRef.current
    ) {
      return;
    }
    const basePose = basePoseRef.current;
    const liveAgentPose =
      focusKind === "agent" && focusId ? agentPosesRef.current.get(focusId) : undefined;
    const target = new THREE.Vector3(
      liveAgentPose?.x ?? focusAnchorX,
      basePose.target.y,
      liveAgentPose?.z ?? focusAnchorZ,
    );
    const cameraOffset = basePose.position.clone().sub(basePose.target);
    animateTo({
      position: target.clone().add(cameraOffset),
      target,
      zoom: focusKind === "agent" ? 1.72 : 1.38,
    });
  }, [
    agentPosesRef,
    animateTo,
    focusAnchorX,
    focusAnchorZ,
    focusId,
    focusKind,
    focusRevision,
  ]);

  useEffect(() => {
    if (lastResetRevisionRef.current === resetRevision) return;
    lastResetRevisionRef.current = resetRevision;
    if (basePoseRef.current) animateTo(cloneCameraPose(basePoseRef.current));
  }, [animateTo, resetRevision]);

  useEffect(() => {
    const { camera, gl } = getThreeState();
    if (!(camera instanceof THREE.OrthographicCamera)) return;
    const canvas = gl.domElement;
    const groundPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();
    let drag:
      | {
          anchor: THREE.Vector3;
          pointerId: number;
          startX: number;
          startY: number;
          moved: boolean;
        }
      | undefined;
    let suppressClickUntil = 0;

    const projectToGround = (event: PointerEvent): THREE.Vector3 | null => {
      const rect = canvas.getBoundingClientRect();
      pointer.set(
        ((event.clientX - rect.left) / Math.max(1, rect.width)) * 2 - 1,
        -((event.clientY - rect.top) / Math.max(1, rect.height)) * 2 + 1,
      );
      camera.updateMatrixWorld();
      raycaster.setFromCamera(pointer, camera);
      return raycaster.ray.intersectPlane(groundPlane, new THREE.Vector3());
    };

    const handlePointerDown = (event: PointerEvent) => {
      if (event.button !== 0 || event.pointerType !== "mouse") return;
      const anchor = projectToGround(event);
      if (!anchor) return;
      drag = {
        anchor,
        pointerId: event.pointerId,
        startX: event.clientX,
        startY: event.clientY,
        moved: false,
      };
      canvas.setPointerCapture(event.pointerId);
      canvas.style.cursor = "grabbing";
    };

    const handlePointerMove = (event: PointerEvent) => {
      if (!drag || drag.pointerId !== event.pointerId) return;
      const distance = Math.hypot(event.clientX - drag.startX, event.clientY - drag.startY);
      if (distance < 3) return;
      drag.moved = true;
      const point = projectToGround(event);
      if (!point) return;
      event.preventDefault();
      animationRef.current = null;
      const translation = drag.anchor.clone().sub(point);
      camera.position.add(translation);
      lookTargetRef.current.add(translation);
      camera.lookAt(lookTargetRef.current);
      camera.updateMatrixWorld();
      invalidate();
    };

    const endPointerDrag = (event: PointerEvent) => {
      if (!drag || drag.pointerId !== event.pointerId) return;
      if (drag.moved) suppressClickUntil = performance.now() + 250;
      if (canvas.hasPointerCapture(event.pointerId)) canvas.releasePointerCapture(event.pointerId);
      drag = undefined;
      canvas.style.cursor = "grab";
    };

    const suppressClickAfterDrag = (event: MouseEvent) => {
      if (performance.now() > suppressClickUntil) return;
      suppressClickUntil = 0;
      event.preventDefault();
      event.stopImmediatePropagation();
    };

    const handleWheel = (event: WheelEvent) => {
      if (window.innerWidth < 1024 && !event.ctrlKey && !event.metaKey) return;
      event.preventDefault();
      animationRef.current = null;
      const unit = event.deltaMode === WheelEvent.DOM_DELTA_LINE ? 16 : 1;
      camera.zoom = calculateVoxelCameraZoom(camera.zoom, event.deltaY * unit);
      camera.updateProjectionMatrix();
      invalidate();
    };

    canvas.addEventListener("pointerdown", handlePointerDown);
    canvas.addEventListener("pointermove", handlePointerMove);
    canvas.addEventListener("pointerup", endPointerDrag);
    canvas.addEventListener("pointercancel", endPointerDrag);
    canvas.addEventListener("click", suppressClickAfterDrag, { capture: true });
    canvas.addEventListener("wheel", handleWheel, { passive: false });
    return () => {
      canvas.removeEventListener("pointerdown", handlePointerDown);
      canvas.removeEventListener("pointermove", handlePointerMove);
      canvas.removeEventListener("pointerup", endPointerDrag);
      canvas.removeEventListener("pointercancel", endPointerDrag);
      canvas.removeEventListener("click", suppressClickAfterDrag, { capture: true });
      canvas.removeEventListener("wheel", handleWheel);
    };
  }, [getThreeState, invalidate]);

  useFrame(() => {
    const camera = getThreeState().camera;
    if (!(camera instanceof THREE.OrthographicCamera) || !animationRef.current) return;
    const animation = animationRef.current;
    const progress = Math.min(1, (performance.now() - animation.startedAt) / animation.durationMs);
    const eased = easeOutQuint(progress);
    camera.position.lerpVectors(animation.from.position, animation.to.position, eased);
    lookTargetRef.current.lerpVectors(animation.from.target, animation.to.target, eased);
    camera.zoom = THREE.MathUtils.lerp(animation.from.zoom, animation.to.zoom, eased);
    camera.lookAt(lookTargetRef.current);
    camera.updateProjectionMatrix();
    camera.updateMatrixWorld();
    if (progress < 1) invalidate();
    else animationRef.current = null;
  });

  return null;
}

function usePrefersReducedMotion(): boolean {
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false);

  useEffect(() => {
    const mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    const updatePreference = () => setPrefersReducedMotion(mediaQuery.matches);
    updatePreference();
    mediaQuery.addEventListener("change", updatePreference);
    return () => mediaQuery.removeEventListener("change", updatePreference);
  }, []);

  return prefersReducedMotion;
}

function cloneCameraPose(pose: CameraPose): CameraPose {
  return {
    position: pose.position.clone(),
    target: pose.target.clone(),
    zoom: pose.zoom,
  };
}

function toThreeVector(vector: VoxelVector3): THREE.Vector3 {
  return new THREE.Vector3(vector.x, vector.y, vector.z);
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
  const material = VOXEL_MATERIAL_CLASS_SPECS[batch.materialClass];

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
      mesh.setColorAt(index, new THREE.Color(VOXEL_MATERIAL_SPECS[block.material].color));
    });
    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
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
      <BatchGeometry kind={batch.geometry} />
      <meshStandardMaterial
        color={material.color}
        roughness={material.roughness}
        metalness={material.metalness ?? 0}
        emissive={material.emissive ?? 0x000000}
        emissiveIntensity={material.emissiveIntensity ?? 0}
      />
    </instancedMesh>
  );
}

function SelectionLayer({
  locationAnchor,
  agentAnchor,
  agentId,
  agentPosesRef,
}: {
  locationAnchor?: VoxelSelectionAnchor;
  agentAnchor?: VoxelSelectionAnchor;
  agentId?: string | null;
  agentPosesRef: AgentPoseMap;
}) {
  return (
    <>
      {locationAnchor ? <SelectionMarker anchor={locationAnchor} opacity={0.48} /> : null}
      {agentAnchor && agentId ? (
        <AgentSelectionMarker
          agentId={agentId}
          anchor={agentAnchor}
          agentPosesRef={agentPosesRef}
        />
      ) : null}
    </>
  );
}

function AgentSelectionMarker({
  agentId,
  anchor,
  agentPosesRef,
}: {
  agentId: string;
  anchor: VoxelSelectionAnchor;
  agentPosesRef: AgentPoseMap;
}) {
  const markerRef = useRef<THREE.Mesh>(null);

  useLayoutEffect(() => {
    const marker = markerRef.current;
    if (!marker) return;
    const pose = agentPosesRef.current.get(agentId);
    marker.position.set(
      pose?.x ?? anchor.position.x,
      (pose?.y ?? 0) + anchor.position.y,
      pose?.z ?? anchor.position.z,
    );
  }, [agentId, agentPosesRef, anchor.position.x, anchor.position.y, anchor.position.z]);

  useFrame(() => {
    const marker = markerRef.current;
    const pose = agentPosesRef.current.get(agentId);
    if (!marker || !pose) return;
    marker.position.set(pose.x, pose.y + anchor.position.y, pose.z);
  });

  return (
    <mesh ref={markerRef} scale={[anchor.size.x, anchor.size.y, anchor.size.z]} receiveShadow>
      <boxGeometry args={[1, 1, 1]} />
      <meshBasicMaterial
        color={VOXEL_MATERIAL_COLORS.highlight}
        transparent
        opacity={0.82}
        depthWrite={false}
      />
    </mesh>
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
    const materialClass = getVoxelMaterialClass(block.material);
    const key = `${block.geometry}:${materialClass}:${Number(block.castShadow)}:${Number(block.receiveShadow)}`;
    const batch = batches.get(key) ?? {
      key,
      materialClass,
      geometry: block.geometry,
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

function ResetCameraIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 20 20" fill="none" className="h-4 w-4">
      <path
        d="M15.6 7.1A6 6 0 1 0 16 11M15.6 7.1V3.8m0 3.3h-3.3"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function StageEventsIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 20 20" fill="none" className="h-4 w-4">
      <path
        d="M4.2 5.3h11.6v7.5H9.4l-3.1 2.3v-2.3H4.2V5.3Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      <path
        d="M7 8h6M7 10.3h3.8"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}
