import type { SceneAgent, SceneWorld } from "@/lib/world-scene-adapter";

import { buildVoxelPlots, findPlotForLocation } from "./plot-layout";
import { resolveAgentAppearance } from "./agent-appearance";
import { resolveReadyWorldAsset } from "./asset-registry";
import { buildLocationPrefab } from "./prefabs";
import { buildRoadGraph } from "./road-graph";
import type {
  VoxelAgentPlan,
  VoxelAssetPlacement,
  VoxelBlock,
  VoxelBounds,
  VoxelHitTarget,
  VoxelGeometryKind,
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
    geometry?: VoxelGeometryKind;
  },
) => VoxelBlock;

export function buildVoxelScenePlan(sceneWorld: SceneWorld): VoxelScenePlan {
  const blocks: VoxelBlock[] = [];
  const assets: VoxelAssetPlacement[] = [];
  let blockIndex = 0;
  const createBlock: BlockWriter = (prefix, position, size, material, options = {}) => {
    const block = {
      id: `${prefix}-${blockIndex}`,
      position: { x: position[0], y: position[1], z: position[2] },
      size: { x: size[0], y: size[1], z: size[2] },
      material,
      geometry: options.geometry ?? "box",
      rotationY: options.rotationY ?? 0,
      castShadow: options.castShadow ?? true,
      receiveShadow: options.receiveShadow ?? true,
      hitTarget: options.hitTarget,
    } satisfies VoxelBlock;
    blockIndex += 1;
    return block;
  };
  const addBlock: BlockWriter = (...args) => {
    const block = createBlock(...args);
    blocks.push(block);
    return block;
  };

  const plots = buildVoxelPlots(sceneWorld.locations, sceneWorld.navigation);
  const roads = buildRoadGraph(plots, sceneWorld.navigation);
  const groundFrame = buildGround(addBlock, plots, roads);
  buildPerimeterLandscape(addBlock, groundFrame);
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
    const fallbackBlocks = prefab.blocks.map((block) =>
      createBlock(
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
          geometry: block.geometry,
        },
      ),
    );
    const asset = resolveReadyWorldAsset(
      location.locationType,
      location.visual.visualPreset,
    );
    if (asset) {
      const scaleTarget = asset.scaleTo === "plot" ? plotItem.size : plotItem.footprint;
      assets.push({
        assetId: asset.id,
        fallbackBlocks,
        locationId: location.id,
        position: { x: plotItem.center.x, y: 0, z: plotItem.center.z },
        rotationY: fallbackBlocks[0]?.rotationY ?? 0,
        scale: {
          x: scaleTarget.width / asset.authoredSize.width,
          y: 1,
          z: scaleTarget.depth / asset.authoredSize.depth,
        },
        uri: asset.uri,
      });
    } else {
      blocks.push(...fallbackBlocks);
    }
    buildPlotDetails(addBlock, plotItem, target);
    locationAnchors[location.id] = {
      position: { x: plotItem.center.x, y: 0.13, z: plotItem.center.z },
      size: { x: plotItem.size.width, y: 0.04, z: plotItem.size.depth },
    };
  }

  const agents = buildAgents(sceneWorld.agents, plots);
  const agentAnchors = Object.fromEntries(agents.map((agent) => [agent.id, agent.anchor]));
  return {
    blocks,
    assets,
    agents,
    bounds: calculateBounds([...blocks, ...assets.flatMap((asset) => asset.fallbackBlocks)]),
    plots,
    roads,
    locationAnchors,
    agentAnchors,
  };
}

type GroundFrame = {
  centerX: number;
  centerZ: number;
  depth: number;
  width: number;
};

function buildGround(
  addBlock: BlockWriter,
  plots: VoxelPlot[],
  roads: VoxelRoadTile[],
): GroundFrame {
  const xValues = [
    ...plots.flatMap((plotItem) => [
      plotItem.center.x - plotItem.size.width / 2,
      plotItem.center.x + plotItem.size.width / 2,
    ]),
    ...roads.map((road) => road.x),
  ];
  const zValues = [
    ...plots.flatMap((plotItem) => [
      plotItem.center.z - plotItem.size.depth / 2,
      plotItem.center.z + plotItem.size.depth / 2,
    ]),
    ...roads.map((road) => road.z),
  ];
  const minX = Math.min(...xValues, -2) - 1.6;
  const maxX = Math.max(...xValues, 2) + 1.6;
  const minZ = Math.min(...zValues, -2) - 1.6;
  const maxZ = Math.max(...zValues, 2) + 1.6;
  const frame = {
    centerX: (minX + maxX) / 2,
    centerZ: (minZ + maxZ) / 2,
    width: Math.max(10, maxX - minX),
    depth: Math.max(10, maxZ - minZ),
  };

  addBlock("ground", [frame.centerX, -0.08, frame.centerZ], [frame.width, 0.16, frame.depth], "grass", {
    castShadow: false,
  });
  for (const [offsetX, offsetZ, width, depth] of [
    [-0.3, -0.28, 0.34, 0.26],
    [0.32, -0.3, 0.28, 0.3],
    [-0.3, 0.32, 0.26, 0.28],
    [0.28, 0.3, 0.36, 0.24],
  ] as const) {
    addBlock("ground-patch", [
      frame.centerX + frame.width * offsetX,
      0.005,
      frame.centerZ + frame.depth * offsetZ,
    ], [frame.width * width, 0.02, frame.depth * depth], "grassAlt", {
      castShadow: false,
      geometry: "cylinder",
    });
  }
  addBlock("ground-base", [frame.centerX, -0.24, frame.centerZ], [frame.width + 0.4, 0.32, frame.depth + 0.4], "groundBase", {
    castShadow: false,
  });
  return frame;
}

function buildPerimeterLandscape(addBlock: BlockWriter, frame: GroundFrame): void {
  const edgeTrees = [
    [-0.38, -0.35, 1.2],
    [0.4, -0.34, 0.92],
    [-0.4, 0.34, 0.82],
    [0.38, 0.36, 1.08],
    [0.45, 0.04, 0.72],
  ] as const;
  for (const [offsetX, offsetZ, scale] of edgeTrees) {
    const x = frame.centerX + frame.width * offsetX;
    const z = frame.centerZ + frame.depth * offsetZ;
    addBlock("landscape-tree", [x, 0.42 * scale, z], [0.18 * scale, 0.84 * scale, 0.18 * scale], "trunk", {
      geometry: "cylinder",
    });
    addBlock("landscape-tree", [x, 1.1 * scale, z], [0.92 * scale, 0.8 * scale, 0.92 * scale], "leaf", {
      geometry: "icosphere",
    });
    addBlock("landscape-tree", [x - 0.18 * scale, 1.38 * scale, z - 0.08 * scale], [0.62 * scale, 0.52 * scale, 0.62 * scale], "leafLight", {
      geometry: "icosphere",
    });
  }
}

function buildRoads(addBlock: BlockWriter, roads: VoxelRoadTile[]): void {
  for (const road of roads) {
    const roadWidth = road.role === "connector" ? 0.96 : 0.99;
    const geometry = isRoundedRoadTile(road) ? "cylinder" : "box";
    addBlock("road-curb", [road.x, 0.02, road.z], [1.04, 0.08, 1.04], "curb", {
      castShadow: false,
      geometry,
    });
    addBlock("road", [road.x, 0.08, road.z], [roadWidth, 0.06, roadWidth], "road", {
      castShadow: false,
      geometry,
    });
    if (road.role !== "connector" && Math.abs(road.x * 31 + road.z * 17) % 3 === 0) {
      addBlock(
        "road-detail",
        [road.x - 0.18, 0.13, road.z + 0.12],
        [0.22, 0.025, 0.18],
        "roadDetail",
        { castShadow: false },
      );
    }
  }
}

function isRoundedRoadTile(road: VoxelRoadTile): boolean {
  const { north, east, south, west } = road.connections;
  const connectionCount = [north, east, south, west].filter(Boolean).length;
  const isStraight = (north && south && !east && !west) || (east && west && !north && !south);
  return road.role === "plaza" || (connectionCount === 2 && !isStraight);
}

function buildPlotDetails(
  addBlock: BlockWriter,
  plotItem: VoxelPlot,
  hitTarget: VoxelHitTarget,
): void {
  const lamp = plotItem.decorationAnchors.find((anchor) => anchor.kind === "lamp");
  if (lamp) {
    addBlock("street-lamp", [lamp.x, 0.48, lamp.z], [0.08, 0.92, 0.08], "trouser", {
      geometry: "cylinder",
      hitTarget,
    });
    addBlock("street-lamp", [lamp.x, 0.98, lamp.z], [0.3, 0.22, 0.3], "roofBlue", {
      geometry: "cone",
      hitTarget,
      rotationY: Math.PI / 4,
    });
    addBlock("street-lamp", [lamp.x, 0.91, lamp.z], [0.14, 0.14, 0.14], "flower", {
      geometry: "icosphere",
      hitTarget,
    });
  }

  if (plotItem.district !== "green" && plotItem.district !== "center") {
    const tree = plotItem.decorationAnchors.find((anchor) => anchor.kind === "tree");
    if (tree) {
      addBlock("street-tree", [tree.x, 0.34, tree.z], [0.14, 0.68, 0.14], "trunk", {
        geometry: "cylinder",
        hitTarget,
      });
      addBlock("street-tree", [tree.x, 0.9, tree.z], [0.68, 0.72, 0.68], "leaf", {
        geometry: "icosphere",
        hitTarget,
      });
    }
  }

  const flowers = plotItem.decorationAnchors.find((anchor) => anchor.kind === "flowers");
  if (flowers) {
    addBlock("plot-flowers", [flowers.x, 0.2, flowers.z], [0.18, 0.18, 0.18], "flowerPink", {
      geometry: "icosphere",
      hitTarget,
    });
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
