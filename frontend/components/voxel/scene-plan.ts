import type { SceneAgent, SceneWorld } from "@/lib/world-scene-adapter";

import { buildVoxelPlots, findPlotForLocation } from "./plot-layout";
import { resolveAgentAppearance } from "./agent-appearance";
import { buildLocationPrefab } from "./prefabs";
import { buildRoadGraph } from "./road-graph";
import type {
  VoxelAgentPlan,
  VoxelBlock,
  VoxelBounds,
  VoxelHitTarget,
  VoxelMaterialKey,
  VoxelPlot,
  VoxelRoadTile,
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
    rotationY?: number;
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
      rotationY: options.rotationY ?? 0,
      castShadow: options.castShadow ?? true,
      receiveShadow: options.receiveShadow ?? true,
      hitTarget: options.hitTarget,
    });
    blockIndex += 1;
  };

  const plots = buildVoxelPlots(sceneWorld.locations, sceneWorld.navigation);
  const roads = buildRoadGraph(plots, sceneWorld.navigation);
  buildGround(addBlock);
  buildRoads(addBlock, roads);

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
    const prefab = buildLocationPrefab(location, plotItem);
    for (const block of prefab.blocks) {
      addBlock(
        `location-${location.id}`,
        [
          plotItem.center.x + block.position.x,
          block.position.y,
          plotItem.center.z + block.position.z,
        ],
        [block.size.x, block.size.y, block.size.z],
        block.material,
        {
          castShadow: block.castShadow,
          receiveShadow: block.receiveShadow,
          hitTarget: target,
          rotationY: block.rotationY,
        },
      );
    }
    locationAnchors[location.id] = {
      position: { x: plotItem.center.x, y: 0.13, z: plotItem.center.z },
      size: { x: plotItem.size.width, y: 0.04, z: plotItem.size.depth },
    };
  }

  const agents = buildAgents(sceneWorld.agents, plots);
  const agentAnchors = Object.fromEntries(agents.map((agent) => [agent.id, agent.anchor]));
  return {
    blocks,
    agents,
    bounds: calculateBounds(blocks),
    plots,
    roads,
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

function buildRoads(addBlock: BlockWriter, roads: VoxelRoadTile[]): void {
  for (const road of roads) {
    const roadWidth = road.role === "connector" ? 0.88 : road.role === "main" ? 0.94 : 0.98;
    addBlock("road-curb", [road.x, 0.02, road.z], [1.01, 0.08, 1.01], "curb", {
      castShadow: false,
    });
    addBlock("road", [road.x, 0.08, road.z], [roadWidth, 0.06, roadWidth], "road", {
      castShadow: false,
    });
    if (road.role !== "connector") {
      addBlock(
        "road-detail",
        [road.x - 0.18, 0.13, road.z + 0.12],
        [0.22, 0.025, 0.18],
        "flower",
        { castShadow: false },
      );
      addBlock(
        "road-detail",
        [road.x + 0.22, 0.13, road.z - 0.16],
        [0.18, 0.025, 0.16],
        "roadDetail",
        { castShadow: false },
      );
    }
  }
}

function buildAgents(
  agents: SceneAgent[],
  plots: VoxelPlot[],
): VoxelAgentPlan[] {
  const agentPlans: VoxelAgentPlan[] = [];
  for (const agent of agents) {
    const plotItem = findPlotForLocation(plots, agent.locationId);
    if (!plotItem) continue;
    const anchor = plotItem.agentAnchors[agent.slotIndex % plotItem.agentAnchors.length];
    agentPlans.push({
      id: agent.id,
      source: agent,
      anchor: {
        position: { x: anchor.x, y: 0.04, z: anchor.z },
        size: { x: 0.46, y: 0.04, z: 0.46 },
      },
      appearance: resolveAgentAppearance(agent.id),
    });
  }
  return agentPlans;
}

function calculateBounds(blocks: VoxelBlock[]): VoxelBounds {
  return blocks.reduce<VoxelBounds>(
    (bounds, block) => {
      const cos = Math.abs(Math.cos(block.rotationY));
      const sin = Math.abs(Math.sin(block.rotationY));
      const halfX = (block.size.x * cos + block.size.z * sin) / 2;
      const halfZ = (block.size.x * sin + block.size.z * cos) / 2;
      return {
        minX: Math.min(bounds.minX, block.position.x - halfX),
        maxX: Math.max(bounds.maxX, block.position.x + halfX),
        minY: Math.min(bounds.minY, block.position.y - block.size.y / 2),
        maxY: Math.max(bounds.maxY, block.position.y + block.size.y / 2),
        minZ: Math.min(bounds.minZ, block.position.z - halfZ),
        maxZ: Math.max(bounds.maxZ, block.position.z + halfZ),
      };
    },
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
