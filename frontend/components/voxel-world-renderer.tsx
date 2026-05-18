"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";

import type { SceneAgent, SceneLocation, SceneWorld } from "@/lib/world-scene-adapter";

type Props = {
  sceneWorld: SceneWorld;
  highlightedLocationId?: string | null;
  highlightedAgentId?: string | null;
  onAgentClick?: (agentId: string) => void;
  onLocationClick?: (locationId: string) => void;
};

type VoxelSlot = {
  x: number;
  z: number;
};

const LOCATION_SLOTS: Record<string, VoxelSlot> = {
  home: { x: -3, z: 3 },
  dorm: { x: -4, z: 4 },
  cafe: { x: 0, z: 4 },
  shop: { x: 3, z: 4 },
  plaza: { x: 0, z: 0 },
  square: { x: 0, z: 0 },
  office: { x: 4, z: -1 },
  library: { x: 2, z: -4 },
  lecture_hall: { x: 4, z: -4 },
  park: { x: -4, z: -2 },
  grove: { x: -5, z: -4 },
  quad: { x: -2, z: -2 },
};

const FALLBACK_SLOTS: VoxelSlot[] = [
  { x: -2, z: 2 },
  { x: 2, z: 2 },
  { x: -2, z: -3 },
  { x: 4, z: 1 },
  { x: -5, z: 1 },
  { x: 5, z: -2 },
];

const palette = {
  grass: 0x8fcf72,
  grassAlt: 0x9ed682,
  road: 0xd8c18d,
  roadDark: 0xb79a67,
  curb: 0x9f875f,
  plot: 0xcfe2b8,
  shadow: 0x6d7f62,
  wallWarm: 0xe8c58e,
  wallCool: 0xaec7db,
  wallStone: 0xbeb9a8,
  roofRed: 0xa84d58,
  roofBlue: 0x4b6f9f,
  roofGreen: 0x4f815b,
  glass: 0x74c6d8,
  wood: 0x7d5437,
  leaf: 0x4f9f57,
  leafLight: 0x73bf62,
  trunk: 0x7b5535,
  flower: 0xf2d35b,
  agent: 0xf47f42,
  agentTalking: 0xf5a142,
  agentResting: 0x9b7fe0,
  agentMoving: 0x48a9da,
  agentWorking: 0x4ac878,
};

export function VoxelWorldRenderer({
  sceneWorld,
  highlightedLocationId,
  highlightedAgentId,
  onAgentClick,
  onLocationClick,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const callbacksRef = useRef({ onAgentClick, onLocationClick });

  useEffect(() => {
    callbacksRef.current = { onAgentClick, onLocationClick };
  }, [onAgentClick, onLocationClick]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xeef5e8);

    const camera = new THREE.OrthographicCamera(-8, 8, 5.5, -5.5, 0.1, 100);
    camera.position.set(8.5, 7.2, 8.5);
    camera.lookAt(0, 0.2, 0);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFShadowMap;
    renderer.domElement.style.width = "100%";
    renderer.domElement.style.height = "100%";
    container.appendChild(renderer.domElement);

    const ambient = new THREE.HemisphereLight(0xffffff, 0x9fb18d, 2.2);
    scene.add(ambient);
    const sun = new THREE.DirectionalLight(0xffffff, 2.4);
    sun.position.set(6, 10, 5);
    sun.castShadow = true;
    sun.shadow.mapSize.set(2048, 2048);
    scene.add(sun);

    const worldGroup = new THREE.Group();
    scene.add(worldGroup);

    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();
    const clickable: THREE.Object3D[] = [];

    const renderWorld = () => {
      clickable.length = 0;
      worldGroup.clear();
      buildGround(worldGroup);
      buildRoads(worldGroup);
      buildLocations(worldGroup, sceneWorld.locations, highlightedLocationId, clickable);
      buildAgents(worldGroup, sceneWorld.agents, sceneWorld.locations, highlightedAgentId, clickable);
      renderer.render(scene, camera);
    };

    const resize = () => {
      const width = container.clientWidth || 800;
      const height = container.clientHeight || 600;
      const aspect = width / Math.max(1, height);
      const viewHeight = 9.6;
      camera.left = (-viewHeight * aspect) / 2;
      camera.right = (viewHeight * aspect) / 2;
      camera.top = viewHeight / 2;
      camera.bottom = -viewHeight / 2;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height, false);
      renderer.render(scene, camera);
    };

    const handlePointerDown = (event: PointerEvent) => {
      const bounds = renderer.domElement.getBoundingClientRect();
      pointer.x = ((event.clientX - bounds.left) / bounds.width) * 2 - 1;
      pointer.y = -(((event.clientY - bounds.top) / bounds.height) * 2 - 1);
      raycaster.setFromCamera(pointer, camera);
      const hit = raycaster.intersectObjects(clickable, true)[0]?.object;
      const target = findClickableTarget(hit);
      if (target?.userData.kind === "location") {
        callbacksRef.current.onLocationClick?.(target.userData.id as string);
      }
      if (target?.userData.kind === "agent") {
        callbacksRef.current.onAgentClick?.(target.userData.id as string);
      }
    };

    const observer = new ResizeObserver(resize);
    observer.observe(container);
    renderer.domElement.addEventListener("pointerdown", handlePointerDown);
    renderWorld();
    resize();

    return () => {
      observer.disconnect();
      renderer.domElement.removeEventListener("pointerdown", handlePointerDown);
      renderer.dispose();
      container.replaceChildren();
    };
  }, [highlightedAgentId, highlightedLocationId, sceneWorld]);

  return (
    <div
      ref={containerRef}
      data-testid="phaser-game-container"
      className="relative h-full min-h-[560px] w-full overflow-hidden rounded-2xl border border-emerald-100 bg-[#eef5e8] shadow-xs"
    />
  );
}

function buildGround(group: THREE.Group): void {
  for (let x = -7; x <= 7; x += 1) {
    for (let z = -7; z <= 7; z += 1) {
      addBox(group, x, -0.08, z, 0.96, 0.16, 0.96, (x + z) % 2 === 0 ? palette.grass : palette.grassAlt);
    }
  }
  addBox(group, 0, -0.2, 0, 15.8, 0.24, 15.8, 0x6fa762);
}

function buildRoads(group: THREE.Group): void {
  const roads = [
    ...range(-6, 6).map((x) => [x, 0]),
    ...range(-5, 5).map((z) => [0, z]),
    ...range(-4, 4).map((x) => [x, 4]),
    [-3, 3],
    [4, 2],
    [3, -3],
  ];
  for (const [x, z] of roads) {
    addBox(group, x, 0.02, z, 0.96, 0.08, 0.96, palette.curb).receiveShadow = true;
    addBox(group, x, 0.08, z, 0.82, 0.06, 0.82, palette.road).receiveShadow = true;
    addBox(group, x - 0.18, 0.13, z + 0.12, 0.22, 0.025, 0.18, 0xf0dfad);
    addBox(group, x + 0.22, 0.13, z - 0.16, 0.18, 0.025, 0.16, 0xc9ad78);
  }
}

function buildLocations(
  group: THREE.Group,
  locations: SceneLocation[],
  highlightedLocationId: string | null | undefined,
  clickable: THREE.Object3D[],
): void {
  locations.forEach((location, index) => {
    const slot = resolveSlot(location, locations, index);
    addBox(group, slot.x, 0.03, slot.z, 1.8, 0.08, 1.8, palette.plot);
    if (isGreenLocation(location)) {
      const park = buildPark(location, slot, highlightedLocationId === location.id);
      park.userData = { kind: "location", id: location.id };
      group.add(park);
      clickable.push(park);
      return;
    }
    const building = buildBuilding(location, slot, highlightedLocationId === location.id);
    building.userData = { kind: "location", id: location.id };
    group.add(building);
    clickable.push(building);
  });
}

function buildBuilding(location: SceneLocation, slot: VoxelSlot, highlighted: boolean): THREE.Group {
  const building = new THREE.Group();
  building.position.set(slot.x, 0, slot.z);
  const type = location.visual.visualPreset ?? location.locationType;
  const height = type.includes("office") || type.includes("tower") ? 1.7 : 1.1;
  const wall = getBuildingWallColor(type);
  const roof = getBuildingRoofColor(type);
  addBox(building, 0, height / 2, 0, 1.1, height, 1.1, wall);
  addVoxelRoof(building, height, type, roof);
  addBox(building, 0, 0.08, 0, 1.28, 0.16, 1.28, palette.shadow);
  addBox(building, -0.58, height * 0.58, 0.02, 0.05, 0.42, 0.72, 0xffffff);
  addBox(building, 0.58, height * 0.52, -0.02, 0.05, 0.4, 0.68, 0x6f8068);
  addBox(building, 0, 0.42, -0.57, 0.3, 0.52, 0.06, palette.wood);
  addWindowRow(building, height, type);
  addBuildingDetails(building, height, type);
  if (highlighted) {
    addBox(building, 0, 0.12, 0, 1.9, 0.04, 1.9, 0xfef08a);
  }
  return building;
}

function addVoxelRoof(group: THREE.Group, height: number, type: string, color: number): void {
  if (type.includes("office") || type.includes("tower")) {
    addBox(group, 0, height + 0.12, 0, 1.24, 0.24, 1.24, color);
    addBox(group, 0, height + 0.3, 0, 0.76, 0.16, 0.76, 0x31527d);
    return;
  }
  addBox(group, 0, height + 0.12, 0, 1.46, 0.18, 1.32, color);
  addBox(group, 0, height + 0.3, 0, 1.1, 0.18, 0.98, color);
  addBox(group, 0, height + 0.45, 0, 0.66, 0.14, 0.58, color);
  if (type.includes("cafe") || type.includes("shop")) {
    addBox(group, 0, height + 0.02, -0.72, 1.18, 0.16, 0.08, 0xf7efd7);
    addBox(group, -0.28, height + 0.03, -0.76, 0.18, 0.18, 0.08, palette.roofRed);
    addBox(group, 0.18, height + 0.03, -0.76, 0.18, 0.18, 0.08, palette.roofRed);
  }
}

function addBuildingDetails(group: THREE.Group, height: number, type: string): void {
  addBox(group, -0.42, height * 0.34, -0.58, 0.18, 0.08, 0.04, 0xffffff);
  addBox(group, 0.42, height * 0.34, -0.58, 0.18, 0.08, 0.04, 0xffffff);
  if (type.includes("library") || type.includes("hall")) {
    for (const x of [-0.42, 0, 0.42]) {
      addBox(group, x, 0.55, -0.62, 0.1, 0.8, 0.08, 0xd8d0bb);
    }
    addBox(group, 0, 0.12, -0.72, 1.2, 0.1, 0.28, 0x928672);
  }
  if (type.includes("home") || type.includes("dorm")) {
    addBox(group, 0.5, 0.9, 0.18, 0.12, 0.5, 0.12, 0x74503c);
  }
}

function buildPark(location: SceneLocation, slot: VoxelSlot, highlighted: boolean): THREE.Group {
  const park = new THREE.Group();
  park.position.set(slot.x, 0, slot.z);
  addBox(park, 0, 0.08, 0, 1.6, 0.12, 1.6, 0x80c76f);
  buildTree(park, -0.42, -0.3, 0.85);
  buildTree(park, 0.34, 0.28, 0.72);
  addBox(park, 0.08, 0.18, -0.56, 0.7, 0.08, 0.18, palette.road);
  addBox(park, -0.55, 0.18, 0.5, 0.16, 0.08, 0.16, palette.flower);
  addBox(park, 0.58, 0.18, -0.2, 0.16, 0.08, 0.16, 0xe879a4);
  if (highlighted) {
    addBox(park, 0, 0.12, 0, 1.9, 0.04, 1.9, 0xfef08a);
  }
  return park;
}

function buildTree(group: THREE.Group, x: number, z: number, scale: number): void {
  addBox(group, x, 0.35 * scale, z, 0.18 * scale, 0.7 * scale, 0.18 * scale, palette.trunk);
  addBox(group, x, 0.92 * scale, z, 0.68 * scale, 0.5 * scale, 0.68 * scale, palette.leaf);
  addBox(group, x - 0.12 * scale, 1.18 * scale, z - 0.08 * scale, 0.42 * scale, 0.34 * scale, 0.42 * scale, palette.leafLight);
}

function addWindowRow(group: THREE.Group, height: number, type: string): void {
  const rows = type.includes("office") || type.includes("tower") ? [0.75, 1.12, 1.48] : [0.72];
  for (const y of rows.filter((row) => row < height)) {
    addBox(group, -0.28, y, -0.59, 0.22, 0.18, 0.04, palette.glass);
    addBox(group, 0.28, y, -0.59, 0.22, 0.18, 0.04, palette.glass);
  }
}

function buildAgents(
  group: THREE.Group,
  agents: SceneAgent[],
  locations: SceneLocation[],
  highlightedAgentId: string | null | undefined,
  clickable: THREE.Object3D[],
): void {
  const locationMap = new Map(locations.map((location, index) => [location.id, resolveSlot(location, locations, index)]));
  for (const agent of agents) {
    const slot = locationMap.get(agent.locationId);
    if (!slot) continue;
    const agentGroup = new THREE.Group();
    const offsetX = -0.45 + (agent.slotIndex % 4) * 0.28;
    const offsetZ = 0.85 + Math.floor(agent.slotIndex / 4) * 0.24;
    agentGroup.position.set(slot.x + offsetX, 0, slot.z + offsetZ);
    const color = getAgentColor(agent.status);
    addBox(agentGroup, 0, 0.34, 0, 0.22, 0.5, 0.18, color);
    addBox(agentGroup, 0, 0.68, 0, 0.2, 0.2, 0.2, 0xffc69c);
    addBox(agentGroup, 0, 0.82, -0.01, 0.22, 0.08, 0.22, 0x2e2a31);
    addBox(agentGroup, -0.07, 0.08, 0, 0.06, 0.16, 0.06, 0x223047);
    addBox(agentGroup, 0.07, 0.08, 0, 0.06, 0.16, 0.06, 0x223047);
    if (highlightedAgentId === agent.id) {
      addBox(agentGroup, 0, 0.04, 0, 0.46, 0.04, 0.46, 0xfef08a);
    }
    agentGroup.userData = { kind: "agent", id: agent.id };
    group.add(agentGroup);
    clickable.push(agentGroup);
  }
}

function isGreenLocation(location: SceneLocation): boolean {
  const type = location.visual.visualPreset ?? location.locationType;
  return type.includes("park") || type.includes("grove") || type.includes("quad");
}

function addBox(
  group: THREE.Group,
  x: number,
  y: number,
  z: number,
  width: number,
  height: number,
  depth: number,
  color: number,
): THREE.Mesh {
  const geometry = new THREE.BoxGeometry(width, height, depth);
  const material = new THREE.MeshLambertMaterial({ color });
  const mesh = new THREE.Mesh(geometry, material);
  mesh.position.set(x, y, z);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  group.add(mesh);
  return mesh;
}

function resolveSlot(location: SceneLocation, locations: SceneLocation[], index: number): VoxelSlot {
  const base = LOCATION_SLOTS[location.locationType] ?? LOCATION_SLOTS[location.visual.visualPreset ?? ""] ?? FALLBACK_SLOTS[index % FALLBACK_SLOTS.length];
  const sameType = locations.filter((candidate) => candidate.locationType === location.locationType).sort((left, right) => left.id.localeCompare(right.id));
  const duplicateIndex = sameType.findIndex((candidate) => candidate.id === location.id);
  if (duplicateIndex <= 0) return base;
  const offsets = [
    { x: 1.5, z: 0 },
    { x: 0, z: 1.5 },
    { x: -1.5, z: 0 },
    { x: 0, z: -1.5 },
  ];
  const offset = offsets[(duplicateIndex - 1) % offsets.length];
  return { x: base.x + offset.x, z: base.z + offset.z };
}

function getBuildingWallColor(type: string): number {
  if (type.includes("office") || type.includes("tower")) return palette.wallCool;
  if (type.includes("library") || type.includes("hall")) return palette.wallStone;
  if (type.includes("park") || type.includes("grove") || type.includes("quad")) return 0x8fcf83;
  return palette.wallWarm;
}

function getBuildingRoofColor(type: string): number {
  if (type.includes("office") || type.includes("tower") || type.includes("library")) return palette.roofBlue;
  if (type.includes("park") || type.includes("grove") || type.includes("quad")) return palette.roofGreen;
  return palette.roofRed;
}

function getAgentColor(status: SceneAgent["status"]): number {
  switch (status) {
    case "moving":
      return palette.agentMoving;
    case "talking":
      return palette.agentTalking;
    case "working":
      return palette.agentWorking;
    case "resting":
      return palette.agentResting;
    default:
      return palette.agent;
  }
}

function findClickableTarget(object: THREE.Object3D | undefined): THREE.Object3D | null {
  let current: THREE.Object3D | null | undefined = object;
  while (current) {
    if (current.userData.kind) return current;
    current = current.parent;
  }
  return null;
}

function range(from: number, to: number): number[] {
  return Array.from({ length: to - from + 1 }, (_, index) => from + index);
}
