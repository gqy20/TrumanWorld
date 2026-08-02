import type { SceneAgent, SceneWorld } from "@/lib/world-scene-adapter";

import { buildVoxelPlots } from "./plot-layout";
import { resolveAgentAppearance } from "./agent-appearance";
import { resolveReadyWorldAsset } from "./asset-registry";
import { buildLocationPrefab } from "./prefabs";
import { buildRoadGraph } from "./road-graph";
import { VOXEL_SCENE_SCALE } from "./scene-scale";
import type {
  VoxelAgentPlan,
  VoxelAssetPlacement,
  VoxelBlock,
  VoxelBlockWriter,
  VoxelBounds,
  VoxelHitTarget,
  VoxelMaterialKey,
  VoxelPlot,
  VoxelPoint,
  VoxelRoadTile,
  VoxelScenePlan,
} from "./types";
import { buildAmbientWorld, type AmbientFrame } from "./ambient-world";

type BlockWriter = VoxelBlockWriter;

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
      layer: options.layer ?? "core",
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
      [plotItem.center.x, VOXEL_SCENE_SCALE.plotHeight / 2, plotItem.center.z],
      [plotItem.size.width, VOXEL_SCENE_SCALE.plotHeight, plotItem.size.depth],
      "plot",
      { castShadow: false, geometry: "cylinder", hitTarget: target },
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
  const focusBlocks = [...blocks, ...assets.flatMap((asset) => asset.fallbackBlocks)];
  buildAmbientWorld(addBlock, groundFrame, sceneWorld.stage);
  return {
    blocks,
    assets,
    agents,
    bounds: calculateBounds([...blocks, ...assets.flatMap((asset) => asset.fallbackBlocks)]),
    focusBounds: calculateBounds(focusBlocks),
    plots,
    roads,
    locationAnchors,
    agentAnchors,
  };
}

type GroundFrame = AmbientFrame;

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
  for (const [offsetX, offsetZ, width, depth, height] of [
    [-0.38, -0.35, 0.24, 0.18, 0.12],
    [0.38, -0.35, 0.22, 0.2, 0.07],
    [-0.38, 0.35, 0.22, 0.22, 0.09],
    [0.38, 0.35, 0.25, 0.18, 0.14],
  ] as const) {
    const x = frame.centerX + frame.width * offsetX;
    const z = frame.centerZ + frame.depth * offsetZ;
    addBlock(
      "landscape-retaining",
      [x, height / 2, z],
      [frame.width * width, height, frame.depth * depth],
      height >= VOXEL_SCENE_SCALE.landscapeTerraceHeight ? "wallStone" : "groundBase",
      { castShadow: false, geometry: "cylinder" },
    );
    addBlock("terrain-terrace", [
      x,
      height + 0.012,
      z,
    ], [frame.width * width - 0.12, 0.024, frame.depth * depth - 0.12], "grassAlt", {
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
    [-0.4, -0.36, 1.12, 0.12],
    [-0.33, -0.34, 0.74, 0.12],
    [0.39, -0.35, 0.88, 0.07],
    [-0.39, 0.35, 0.82, 0.09],
    [0.4, 0.36, 1.08, 0.14],
    [0.45, 0.04, 0.68, 0],
  ] as const;
  for (const [offsetX, offsetZ, scale, elevation] of edgeTrees) {
    const x = frame.centerX + frame.width * offsetX;
    const z = frame.centerZ + frame.depth * offsetZ;
    addBlock("landscape-tree", [x, elevation + 0.42 * scale, z], [0.18 * scale, 0.84 * scale, 0.18 * scale], "trunk", {
      geometry: "cylinder",
    });
    addBlock("landscape-tree", [x, elevation + 1.1 * scale, z], [0.92 * scale, 0.8 * scale, 0.92 * scale], "leaf", {
      geometry: "icosphere",
    });
    addBlock("landscape-tree", [x - 0.18 * scale, elevation + 1.38 * scale, z - 0.08 * scale], [0.62 * scale, 0.52 * scale, 0.62 * scale], "leafLight", {
      geometry: "icosphere",
    });
    for (const [deltaX, deltaZ, shrubScale] of [
      [-0.42, 0.18, 0.34],
      [0.34, -0.26, 0.26],
    ] as const) {
      addBlock(
        "landscape-shrub",
        [x + deltaX * scale, elevation + 0.12 * shrubScale, z + deltaZ * scale],
        [0.58 * shrubScale, 0.34 * shrubScale, 0.5 * shrubScale],
        shrubScale > 0.3 ? "leaf" : "leafLight",
        { geometry: "icosphere" },
      );
    }
    addBlock(
      "landscape-stone",
      [x + 0.38 * scale, elevation + 0.06, z + 0.24 * scale],
      [0.22 * scale, 0.12, 0.18 * scale],
      "wallStone",
      { geometry: "icosphere" },
    );
  }
}

function buildRoads(addBlock: BlockWriter, roads: VoxelRoadTile[]): void {
  for (const road of roads) {
    const curbWidth = road.role === "plaza"
      ? VOXEL_SCENE_SCALE.roadCurbWidth + 0.1
      : VOXEL_SCENE_SCALE.roadCurbWidth;
    const surfaceWidth = road.role === "plaza"
      ? VOXEL_SCENE_SCALE.roadSurfaceWidth + 0.1
      : VOXEL_SCENE_SCALE.roadSurfaceWidth;
    addBlock("road-curb-node", [road.x, VOXEL_SCENE_SCALE.roadCurbHeight / 2, road.z], [
      curbWidth,
      VOXEL_SCENE_SCALE.roadCurbHeight,
      curbWidth,
    ], "curb", {
      castShadow: false,
      geometry: "cylinder",
    });
    addBlock("road-surface-node", [road.x, VOXEL_SCENE_SCALE.roadCurbHeight + VOXEL_SCENE_SCALE.roadSurfaceHeight / 2, road.z], [
      surfaceWidth,
      VOXEL_SCENE_SCALE.roadSurfaceHeight,
      surfaceWidth,
    ], "road", {
      castShadow: false,
      geometry: "cylinder",
    });

    if (road.connections.east) {
      addRoadConnection(addBlock, road, "east", curbWidth, surfaceWidth);
    }
    if (road.connections.south) {
      addRoadConnection(addBlock, road, "south", curbWidth, surfaceWidth);
    }
    if (road.role !== "connector" && Math.abs(road.x * 31 + road.z * 17) % 3 === 0) {
      addBlock(
        "road-detail",
        [
          road.x - 0.18,
          VOXEL_SCENE_SCALE.roadCurbHeight + VOXEL_SCENE_SCALE.roadSurfaceHeight + 0.006,
          road.z + 0.12,
        ],
        [0.18, 0.012, 0.14],
        "roadDetail",
        { castShadow: false },
      );
    }
  }
}

function addRoadConnection(
  addBlock: BlockWriter,
  road: VoxelRoadTile,
  direction: "east" | "south",
  curbWidth: number,
  surfaceWidth: number,
): void {
  const isHorizontal = direction === "east";
  const x = road.x + (isHorizontal ? 0.5 : 0);
  const z = road.z + (isHorizontal ? 0 : 0.5);
  addBlock("road-curb-segment", [x, VOXEL_SCENE_SCALE.roadCurbHeight / 2 - 0.001, z], [
    isHorizontal ? 1.04 : curbWidth,
    VOXEL_SCENE_SCALE.roadCurbHeight,
    isHorizontal ? curbWidth : 1.04,
  ], "curb", { castShadow: false });
  addBlock("road-surface-segment", [
    x,
    VOXEL_SCENE_SCALE.roadCurbHeight + VOXEL_SCENE_SCALE.roadSurfaceHeight / 2 - 0.001,
    z,
  ], [
    isHorizontal ? 1.04 : surfaceWidth,
    VOXEL_SCENE_SCALE.roadSurfaceHeight,
    isHorizontal ? surfaceWidth : 1.04,
  ], "road", { castShadow: false });
}

function buildPlotDetails(
  addBlock: BlockWriter,
  plotItem: VoxelPlot,
  hitTarget: VoxelHitTarget,
): void {
  buildPlotThreshold(addBlock, plotItem, hitTarget);
  buildDistrictEdge(addBlock, plotItem, hitTarget);
  buildActivityFurniture(addBlock, plotItem, hitTarget);

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
    for (const [deltaX, deltaZ, scale, material] of [
      [-0.08, 0.02, 0.11, "flowerPink"],
      [0.06, 0.05, 0.09, "flower"],
      [0, -0.06, 0.1, "leafLight"],
    ] as const) {
      addBlock(
        "plot-flowers",
        [flowers.x + deltaX, 0.08 + scale / 2, flowers.z + deltaZ],
        [scale, scale, scale],
        material,
        { geometry: "icosphere", hitTarget },
      );
    }
  }
}

function buildActivityFurniture(
  addBlock: BlockWriter,
  plotItem: VoxelPlot,
  hitTarget: VoxelHitTarget,
): void {
  if (plotItem.district === "center") return;

  const orientation = resolvePlotOrientation(plotItem);
  if (plotItem.district === "green" || plotItem.district === "civic") {
    buildActivityBenches(addBlock, plotItem, hitTarget, orientation);
  }

  if (plotItem.district === "commerce" || plotItem.district === "green") {
    const conversationCenter = averagePoints(plotItem.activityAnchors.talking);
    const surfaceMaterial: VoxelMaterialKey = plotItem.district === "green"
      ? "wood"
      : "wallStone";
    addBlock(
      "activity-conversation-base",
      [conversationCenter.x, 0.07, conversationCenter.z],
      [0.24, 0.06, 0.24],
      surfaceMaterial,
      { geometry: "cylinder", hitTarget, castShadow: false },
    );
    addBlock(
      "activity-conversation-post",
      [
        conversationCenter.x,
        VOXEL_SCENE_SCALE.activitySurfaceHeight / 2 + 0.04,
        conversationCenter.z,
      ],
      [0.07, VOXEL_SCENE_SCALE.activitySurfaceHeight, 0.07],
      surfaceMaterial,
      { geometry: "cylinder", hitTarget },
    );
    addBlock(
      "activity-conversation-surface",
      [
        conversationCenter.x,
        VOXEL_SCENE_SCALE.activitySurfaceHeight + 0.05,
        conversationCenter.z,
      ],
      [0.42, 0.07, 0.42],
      surfaceMaterial,
      { geometry: "cylinder", hitTarget },
    );
  }

  buildWorkFixture(addBlock, plotItem, hitTarget, orientation);
}

function buildActivityBenches(
  addBlock: BlockWriter,
  plotItem: VoxelPlot,
  hitTarget: VoxelHitTarget,
  orientation: PlotOrientation,
): void {
  const seatMaterial: VoxelMaterialKey = plotItem.district === "civic"
    ? "wallStone"
    : "wood";
  const resting = plotItem.activityAnchors.resting;
  for (const [side, indices] of [[-1, [0, 2]], [1, [1, 3]]] as const) {
    const center = averagePoints(indices.map((index) => resting[index]));
    addBlock(
      "activity-bench-seat",
      [center.x, VOXEL_SCENE_SCALE.activitySeatHeight + 0.03, center.z],
      [0.24, 0.1, 0.52],
      seatMaterial,
      { hitTarget, rotationY: orientation.rotationY, castShadow: false },
    );
    const back = offsetWorldPoint(center, orientation, side * 0.11, 0);
    addBlock(
      "activity-bench-back",
      [back.x, 0.31, back.z],
      [0.07, 0.3, 0.52],
      seatMaterial,
      { hitTarget, rotationY: orientation.rotationY },
    );
    for (const forwardDistance of [-0.18, 0.18]) {
      const leg = offsetWorldPoint(center, orientation, 0, forwardDistance);
      addBlock(
        "activity-bench-leg",
        [leg.x, 0.1, leg.z],
        [0.08, 0.16, 0.08],
        seatMaterial,
        { hitTarget },
      );
    }
  }
}

function buildWorkFixture(
  addBlock: BlockWriter,
  plotItem: VoxelPlot,
  hitTarget: VoxelHitTarget,
  orientation: PlotOrientation,
): void {
  const workCenter = averagePoints(plotItem.activityAnchors.working);
  if (plotItem.district === "home") {
    const mailbox = offsetWorldPoint(workCenter, orientation, 0.34, 0.02);
    addBlock(
      "activity-mailbox-post",
      [mailbox.x, 0.25, mailbox.z],
      [0.07, 0.44, 0.07],
      "wood",
      { hitTarget },
    );
    addBlock(
      "activity-mailbox",
      [mailbox.x, 0.49, mailbox.z],
      [0.28, 0.2, 0.2],
      "roofRed",
      { hitTarget, rotationY: orientation.rotationY },
    );
    return;
  }

  if (plotItem.district === "green") {
    const crate = offsetWorldPoint(workCenter, orientation, 0.3, -0.04);
    addBlock(
      "activity-tool-crate",
      [crate.x, 0.14, crate.z],
      [0.34, 0.22, 0.26],
      "wood",
      { hitTarget, rotationY: orientation.rotationY },
    );
    addBlock(
      "activity-tool-handle",
      [crate.x, 0.38, crate.z],
      [0.06, 0.34, 0.06],
      "trouser",
      { geometry: "cylinder", hitTarget, rotationY: orientation.rotationY },
    );
    return;
  }

  const surfaceMaterial: VoxelMaterialKey = plotItem.district === "civic"
    ? "wallStone"
    : "wood";
  const counter = offsetWorldPoint(workCenter, orientation, 0, -0.08);
  addBlock(
    "activity-work-surface",
    [counter.x, 0.37, counter.z],
    [0.62, 0.08, 0.2],
    surfaceMaterial,
    { hitTarget, rotationY: orientation.rotationY },
  );
  for (const side of [-1, 1] as const) {
    const leg = offsetWorldPoint(counter, orientation, side * 0.24, 0);
    addBlock(
      "activity-work-leg",
      [leg.x, 0.2, leg.z],
      [0.07, 0.34, 0.07],
      surfaceMaterial,
      { hitTarget },
    );
  }
}

function buildPlotThreshold(
  addBlock: BlockWriter,
  plotItem: VoxelPlot,
  hitTarget: VoxelHitTarget,
): void {
  if (plotItem.district === "center") return;
  const orientation = resolvePlotOrientation(plotItem);
  const footprintReach = resolveFootprintReach(plotItem, orientation);
  const entranceDistance = Math.hypot(
    plotItem.entrance.x - plotItem.center.x,
    plotItem.entrance.z - plotItem.center.z,
  );
  const pathLength = Math.max(0.28, entranceDistance - footprintReach + 0.12);
  const centerDistance = footprintReach + pathLength / 2 - 0.04;
  const center = offsetPlotPoint(plotItem, orientation, 0, centerDistance);
  const width = plotItem.district === "civic" ? 0.58 : 0.46;
  addBlock(
    "plot-threshold",
    [
      center.x,
      VOXEL_SCENE_SCALE.plotHeight + VOXEL_SCENE_SCALE.thresholdPathHeight / 2,
      center.z,
    ],
    [width, VOXEL_SCENE_SCALE.thresholdPathHeight, pathLength],
    plotItem.district === "green" ? "roadDetail" : "paving",
    {
      castShadow: false,
      hitTarget,
      rotationY: orientation.rotationY,
    },
  );
}

function buildDistrictEdge(
  addBlock: BlockWriter,
  plotItem: VoxelPlot,
  hitTarget: VoxelHitTarget,
): void {
  const orientation = resolvePlotOrientation(plotItem);
  if (plotItem.district === "home") {
    for (const side of [-1, 1] as const) {
      const hedge = offsetPlotPoint(
        plotItem,
        orientation,
        side * (plotItem.size.width / 2 - 0.13),
        0.02,
      );
      addBlock(
        "plot-hedge",
        [hedge.x, VOXEL_SCENE_SCALE.hedgeHeight / 2 + 0.025, hedge.z],
        [0.18, VOXEL_SCENE_SCALE.hedgeHeight, plotItem.size.depth * 0.58],
        side < 0 ? "leaf" : "leafLight",
        { hitTarget, rotationY: orientation.rotationY },
      );
    }
    return;
  }

  if (plotItem.district === "civic" || plotItem.district === "commerce") {
    const frontDistance = resolveFootprintReach(plotItem, orientation) + 0.16;
    const lateralDistance = plotItem.district === "civic" ? 0.48 : 0.42;
    for (const side of [-1, 1] as const) {
      const planter = offsetPlotPoint(
        plotItem,
        orientation,
        side * lateralDistance,
        frontDistance,
      );
      addBlock(
        "district-planter",
        [planter.x, 0.09, planter.z],
        [0.3, 0.12, 0.24],
        plotItem.district === "civic" ? "wallStone" : "wood",
        { geometry: "cylinder", hitTarget },
      );
      addBlock(
        "district-planter-green",
        [planter.x, 0.22, planter.z],
        [0.32, 0.22, 0.28],
        side < 0 ? "leaf" : "leafLight",
        { geometry: "icosphere", hitTarget },
      );
    }
    for (const side of [-1, 1] as const) {
      const hedge = offsetPlotPoint(
        plotItem,
        orientation,
        side * (plotItem.size.width / 2 - 0.12),
        -0.16,
      );
      addBlock(
        "district-hedge",
        [hedge.x, 0.1, hedge.z],
        [0.14, 0.16, plotItem.size.depth * 0.34],
        side < 0 ? "leaf" : "leafLight",
        { hitTarget, rotationY: orientation.rotationY },
      );
    }
  }
}

type PlotOrientation = {
  forward: { x: number; z: number };
  right: { x: number; z: number };
  rotationY: number;
};

function resolvePlotOrientation(plotItem: VoxelPlot): PlotOrientation {
  const deltaX = plotItem.entrance.x - plotItem.center.x;
  const deltaZ = plotItem.entrance.z - plotItem.center.z;
  const distance = Math.hypot(deltaX, deltaZ) || 1;
  const forward = { x: deltaX / distance, z: deltaZ / distance };
  return {
    forward,
    right: { x: forward.z, z: -forward.x },
    rotationY: Math.atan2(forward.x, forward.z),
  };
}

function offsetPlotPoint(
  plotItem: VoxelPlot,
  orientation: PlotOrientation,
  rightDistance: number,
  forwardDistance: number,
): { x: number; z: number } {
  return {
    x: plotItem.center.x
      + orientation.right.x * rightDistance
      + orientation.forward.x * forwardDistance,
    z: plotItem.center.z
      + orientation.right.z * rightDistance
      + orientation.forward.z * forwardDistance,
  };
}

function offsetWorldPoint(
  point: VoxelPoint,
  orientation: PlotOrientation,
  rightDistance: number,
  forwardDistance: number,
): VoxelPoint {
  return {
    x: point.x
      + orientation.right.x * rightDistance
      + orientation.forward.x * forwardDistance,
    z: point.z
      + orientation.right.z * rightDistance
      + orientation.forward.z * forwardDistance,
  };
}

function resolveFootprintReach(
  plotItem: VoxelPlot,
  orientation: PlotOrientation,
): number {
  return Math.abs(orientation.forward.x) * plotItem.footprint.width / 2
    + Math.abs(orientation.forward.z) * plotItem.footprint.depth / 2;
}

function buildAgents(
  agents: SceneAgent[],
  plots: VoxelPlot[],
): VoxelAgentPlan[] {
  const agentPlans: VoxelAgentPlan[] = [];
  for (const plotItem of plots) {
    const locationAgents = agents
      .filter((agent) => agent.locationId === plotItem.locationId)
      .sort((left, right) => left.slotIndex - right.slotIndex || left.id.localeCompare(right.id));
    const activityCounts = new Map<SceneAgent["status"], number>();
    const locationPlans = locationAgents.map((agent) => {
      const activityAnchors = resolveActivityAnchors(plotItem, agent.status);
      const activityIndex = activityCounts.get(agent.status) ?? 0;
      activityCounts.set(agent.status, activityIndex + 1);
      const anchor = activityAnchors[activityIndex % activityAnchors.length];
      return {
        id: agent.id,
        source: agent,
        anchor: {
          position: { x: anchor.x, y: VOXEL_SCENE_SCALE.agentAnchorY, z: anchor.z },
          size: { x: 0.46, y: 0.04, z: 0.46 },
        },
        appearance: resolveAgentAppearance(agent.id),
        rotationY: 0,
      } satisfies VoxelAgentPlan;
    });
    const talkingPlans = locationPlans.filter((plan) => plan.source.status === "talking");
    const conversationCenter = talkingPlans.length > 1
      ? averageAgentPosition(talkingPlans)
      : null;
    for (const plan of locationPlans) {
      const target = plan.source.status === "talking" && conversationCenter
        ? conversationCenter
        : plotItem.center;
      plan.rotationY = Math.atan2(
        target.x - plan.anchor.position.x,
        target.z - plan.anchor.position.z,
      );
      agentPlans.push(plan);
    }
  }
  return agentPlans;
}

function resolveActivityAnchors(
  plotItem: VoxelPlot,
  status: SceneAgent["status"],
): VoxelPlot["agentAnchors"] {
  switch (status) {
    case "talking":
      return plotItem.activityAnchors.talking;
    case "working":
      return plotItem.activityAnchors.working;
    case "resting":
      return plotItem.activityAnchors.resting;
    default:
      return plotItem.agentAnchors;
  }
}

function averageAgentPosition(agents: VoxelAgentPlan[]): { x: number; z: number } {
  return {
    x: agents.reduce((sum, agent) => sum + agent.anchor.position.x, 0) / agents.length,
    z: agents.reduce((sum, agent) => sum + agent.anchor.position.z, 0) / agents.length,
  };
}

function averagePoints(points: VoxelPoint[]): VoxelPoint {
  return {
    x: points.reduce((sum, point) => sum + point.x, 0) / points.length,
    z: points.reduce((sum, point) => sum + point.z, 0) / points.length,
  };
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
