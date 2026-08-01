import type { SceneAgent, SceneLocation, SceneWorld } from "@/lib/world-scene-adapter";

import { buildVoxelPlots, findPlotForLocation } from "./plot-layout";
import type {
  VoxelBlock,
  VoxelBounds,
  VoxelHitTarget,
  VoxelMaterialKey,
  VoxelPlot,
  VoxelScenePlan,
} from "./types";

type BlockWriter = (
  prefix: string,
  position: [number, number, number],
  size: [number, number, number],
  material: VoxelMaterialKey,
  options?: {
    castShadow?: boolean;
    receiveShadow?: boolean;
    hitTarget?: VoxelHitTarget;
  },
) => void;

export function buildVoxelScenePlan(sceneWorld: SceneWorld): VoxelScenePlan {
  const blocks: VoxelBlock[] = [];
  let blockIndex = 0;
  const addBlock: BlockWriter = (prefix, position, size, material, options = {}) => {
    blocks.push({
      id: `${prefix}-${blockIndex}`,
      position: { x: position[0], y: position[1], z: position[2] },
      size: { x: size[0], y: size[1], z: size[2] },
      material,
      castShadow: options.castShadow ?? true,
      receiveShadow: options.receiveShadow ?? true,
      hitTarget: options.hitTarget,
    });
    blockIndex += 1;
  };

  const plots = buildVoxelPlots(sceneWorld.locations);
  buildGround(addBlock);
  buildRoads(addBlock);

  const locationAnchors: VoxelScenePlan["locationAnchors"] = {};
  for (const plotItem of plots) {
    const location = plotItem.source;
    const target = { kind: "location", id: location.id } as const;
    addBlock(
      `plot-${location.id}`,
      [plotItem.center.x, 0.03, plotItem.center.z],
      [plotItem.size.width, 0.08, plotItem.size.depth],
      "plot",
      { castShadow: false, hitTarget: target },
    );
    if (isGreenLocation(location)) {
      buildPark(addBlock, location, plotItem, target);
    } else {
      buildBuilding(addBlock, location, plotItem, target);
    }
    locationAnchors[location.id] = {
      position: { x: plotItem.center.x, y: 0.13, z: plotItem.center.z },
      size: { x: plotItem.size.width, y: 0.04, z: plotItem.size.depth },
    };
  }

  const agentAnchors = buildAgents(addBlock, sceneWorld.agents, plots);
  return {
    blocks,
    bounds: calculateBounds(blocks),
    plots,
    locationAnchors,
    agentAnchors,
  };
}

function buildGround(addBlock: BlockWriter): void {
  for (let x = -7; x <= 7; x += 1) {
    for (let z = -7; z <= 7; z += 1) {
      addBlock(
        "ground",
        [x, -0.08, z],
        [0.96, 0.16, 0.96],
        (x + z) % 2 === 0 ? "grass" : "grassAlt",
        { castShadow: false },
      );
    }
  }
  addBlock("ground-base", [0, -0.2, 0], [15.8, 0.24, 15.8], "groundBase", {
    castShadow: false,
  });
}

function buildRoads(addBlock: BlockWriter): void {
  const roads = [
    ...range(-6, 6).map((x) => [x, 0] as const),
    ...range(-5, 5).map((z) => [0, z] as const),
    ...range(-4, 4).map((x) => [x, 4] as const),
    [-3, 3] as const,
    [4, 2] as const,
    [3, -3] as const,
  ];
  for (const [x, z] of roads) {
    addBlock("road-curb", [x, 0.02, z], [0.96, 0.08, 0.96], "curb", {
      castShadow: false,
    });
    addBlock("road", [x, 0.08, z], [0.82, 0.06, 0.82], "road", {
      castShadow: false,
    });
    addBlock("road-detail", [x - 0.18, 0.13, z + 0.12], [0.22, 0.025, 0.18], "flower", {
      castShadow: false,
    });
    addBlock("road-detail", [x + 0.22, 0.13, z - 0.16], [0.18, 0.025, 0.16], "roadDetail", {
      castShadow: false,
    });
  }
}

function buildBuilding(
  addBlock: BlockWriter,
  location: SceneLocation,
  plotItem: VoxelPlot,
  hitTarget: VoxelHitTarget,
): void {
  const type = location.visual.visualPreset ?? location.locationType;
  const height = type.includes("office") || type.includes("tower") ? 1.7 : 1.1;
  const prefix = `location-${location.id}`;
  const add = (
    position: [number, number, number],
    size: [number, number, number],
    material: VoxelMaterialKey,
  ) =>
    addBlock(
      prefix,
      [plotItem.center.x + position[0], position[1], plotItem.center.z + position[2]],
      size,
      material,
      { hitTarget },
    );

  add([0, height / 2, 0], [plotItem.footprint.width, height, plotItem.footprint.depth], getBuildingWallMaterial(type));
  addVoxelRoof(add, height, type, getBuildingRoofMaterial(type));
  add([0, 0.08, 0], [1.28, 0.16, 1.28], "shadow");
  add([-0.58, height * 0.58, 0.02], [0.05, 0.42, 0.72], "white");
  add([0.58, height * 0.52, -0.02], [0.05, 0.4, 0.68], "shadow");
  add([0, 0.42, -0.57], [0.3, 0.52, 0.06], "wood");
  addWindowRow(add, height, type);
  addBuildingDetails(add, height, type);
}

function addVoxelRoof(
  add: (position: [number, number, number], size: [number, number, number], material: VoxelMaterialKey) => void,
  height: number,
  type: string,
  material: VoxelMaterialKey,
): void {
  if (type.includes("office") || type.includes("tower")) {
    add([0, height + 0.12, 0], [1.24, 0.24, 1.24], material);
    add([0, height + 0.3, 0], [0.76, 0.16, 0.76], "roofBlue");
    return;
  }
  add([0, height + 0.12, 0], [1.46, 0.18, 1.32], material);
  add([0, height + 0.3, 0], [1.1, 0.18, 0.98], material);
  add([0, height + 0.45, 0], [0.66, 0.14, 0.58], material);
  if (type.includes("cafe") || type.includes("shop")) {
    add([0, height + 0.02, -0.72], [1.18, 0.16, 0.08], "white");
    add([-0.28, height + 0.03, -0.76], [0.18, 0.18, 0.08], "roofRed");
    add([0.18, height + 0.03, -0.76], [0.18, 0.18, 0.08], "roofRed");
  }
}

function addWindowRow(
  add: (position: [number, number, number], size: [number, number, number], material: VoxelMaterialKey) => void,
  height: number,
  type: string,
): void {
  const rows = type.includes("office") || type.includes("tower") ? [0.75, 1.12, 1.48] : [0.72];
  for (const y of rows.filter((row) => row < height)) {
    add([-0.28, y, -0.59], [0.22, 0.18, 0.04], "glass");
    add([0.28, y, -0.59], [0.22, 0.18, 0.04], "glass");
  }
}

function addBuildingDetails(
  add: (position: [number, number, number], size: [number, number, number], material: VoxelMaterialKey) => void,
  height: number,
  type: string,
): void {
  add([-0.42, height * 0.34, -0.58], [0.18, 0.08, 0.04], "white");
  add([0.42, height * 0.34, -0.58], [0.18, 0.08, 0.04], "white");
  if (type.includes("library") || type.includes("hall")) {
    for (const x of [-0.42, 0, 0.42]) {
      add([x, 0.55, -0.62], [0.1, 0.8, 0.08], "wallStone");
    }
    add([0, 0.12, -0.72], [1.2, 0.1, 0.28], "shadow");
  }
  if (type.includes("home") || type.includes("dorm")) {
    add([0.5, 0.9, 0.18], [0.12, 0.5, 0.12], "wood");
  }
}

function buildPark(
  addBlock: BlockWriter,
  location: SceneLocation,
  plotItem: VoxelPlot,
  hitTarget: VoxelHitTarget,
): void {
  const prefix = `location-${location.id}`;
  const add = (
    position: [number, number, number],
    size: [number, number, number],
    material: VoxelMaterialKey,
  ) =>
    addBlock(
      prefix,
      [plotItem.center.x + position[0], position[1], plotItem.center.z + position[2]],
      size,
      material,
      { hitTarget },
    );

  add([0, 0.08, 0], [plotItem.size.width - 0.4, 0.12, plotItem.size.depth - 0.4], "grass");
  buildTree(add, -0.42, -0.3, 0.85);
  buildTree(add, 0.34, 0.28, 0.72);
  add([0.08, 0.18, -0.56], [0.7, 0.08, 0.18], "road");
  add([-0.55, 0.18, 0.5], [0.16, 0.08, 0.16], "flower");
  add([0.58, 0.18, -0.2], [0.16, 0.08, 0.16], "flowerPink");
}

function buildTree(
  add: (position: [number, number, number], size: [number, number, number], material: VoxelMaterialKey) => void,
  x: number,
  z: number,
  scale: number,
): void {
  add([x, 0.35 * scale, z], [0.18 * scale, 0.7 * scale, 0.18 * scale], "trunk");
  add([x, 0.92 * scale, z], [0.68 * scale, 0.5 * scale, 0.68 * scale], "leaf");
  add(
    [x - 0.12 * scale, 1.18 * scale, z - 0.08 * scale],
    [0.42 * scale, 0.34 * scale, 0.42 * scale],
    "leafLight",
  );
}

function buildAgents(
  addBlock: BlockWriter,
  agents: SceneAgent[],
  plots: VoxelPlot[],
): VoxelScenePlan["agentAnchors"] {
  const agentAnchors: VoxelScenePlan["agentAnchors"] = {};
  for (const agent of agents) {
    const plotItem = findPlotForLocation(plots, agent.locationId);
    if (!plotItem) continue;
    const anchor = plotItem.agentAnchors[agent.slotIndex % plotItem.agentAnchors.length];
    const target = { kind: "agent", id: agent.id } as const;
    const prefix = `agent-${agent.id}`;
    const add = (
      position: [number, number, number],
      size: [number, number, number],
      material: VoxelMaterialKey,
    ) =>
      addBlock(
        prefix,
        [anchor.x + position[0], position[1], anchor.z + position[2]],
        size,
        material,
        { hitTarget: target },
      );

    add([0, 0.34, 0], [0.22, 0.5, 0.18], getAgentMaterial(agent.status));
    add([0, 0.68, 0], [0.2, 0.2, 0.2], "skin");
    add([0, 0.82, -0.01], [0.22, 0.08, 0.22], "hair");
    add([-0.07, 0.08, 0], [0.06, 0.16, 0.06], "trouser");
    add([0.07, 0.08, 0], [0.06, 0.16, 0.06], "trouser");
    agentAnchors[agent.id] = {
      position: { x: anchor.x, y: 0.04, z: anchor.z },
      size: { x: 0.46, y: 0.04, z: 0.46 },
    };
  }
  return agentAnchors;
}

function calculateBounds(blocks: VoxelBlock[]): VoxelBounds {
  return blocks.reduce<VoxelBounds>(
    (bounds, block) => ({
      minX: Math.min(bounds.minX, block.position.x - block.size.x / 2),
      maxX: Math.max(bounds.maxX, block.position.x + block.size.x / 2),
      minY: Math.min(bounds.minY, block.position.y - block.size.y / 2),
      maxY: Math.max(bounds.maxY, block.position.y + block.size.y / 2),
      minZ: Math.min(bounds.minZ, block.position.z - block.size.z / 2),
      maxZ: Math.max(bounds.maxZ, block.position.z + block.size.z / 2),
    }),
    {
      minX: Number.POSITIVE_INFINITY,
      maxX: Number.NEGATIVE_INFINITY,
      minY: Number.POSITIVE_INFINITY,
      maxY: Number.NEGATIVE_INFINITY,
      minZ: Number.POSITIVE_INFINITY,
      maxZ: Number.NEGATIVE_INFINITY,
    },
  );
}

function isGreenLocation(location: SceneLocation): boolean {
  const type = location.visual.visualPreset ?? location.locationType;
  return type.includes("park") || type.includes("grove") || type.includes("quad");
}

function getBuildingWallMaterial(type: string): VoxelMaterialKey {
  if (type.includes("office") || type.includes("tower")) return "wallCool";
  if (type.includes("library") || type.includes("hall")) return "wallStone";
  return "wallWarm";
}

function getBuildingRoofMaterial(type: string): VoxelMaterialKey {
  if (type.includes("office") || type.includes("tower") || type.includes("library")) {
    return "roofBlue";
  }
  if (type.includes("park") || type.includes("grove") || type.includes("quad")) {
    return "roofGreen";
  }
  return "roofRed";
}

function getAgentMaterial(status: SceneAgent["status"]): VoxelMaterialKey {
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

function range(from: number, to: number): number[] {
  return Array.from({ length: to - from + 1 }, (_, index) => from + index);
}
