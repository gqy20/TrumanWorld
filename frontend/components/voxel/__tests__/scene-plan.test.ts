import type { SceneWorld } from "@/lib/world-scene-adapter";

import { buildVoxelScenePlan } from "../scene-plan";

function makeSceneWorld(): SceneWorld {
  return {
    runId: "run-1",
    isRunning: true,
    locations: [
      {
        id: "cafe",
        name: "Cafe",
        locationType: "cafe",
        visual: { visualPreset: "shop" },
        x: 2,
        y: 1,
        capacity: 6,
        occupantCount: 1,
        heat: 2,
      },
      {
        id: "park",
        name: "Park",
        locationType: "park",
        visual: { visualPreset: "grove" },
        x: 0,
        y: 0,
        capacity: 10,
        occupantCount: 0,
        heat: 0,
      },
    ],
    agents: [
      {
        id: "agent-1",
        name: "Mei",
        locationId: "cafe",
        status: "talking",
        slotIndex: 0,
      },
    ],
    activeMovements: [],
    moveTrails: [],
    bubbles: [],
    ambience: { label: "早晨", overlayColor: "#ffffff", isDark: false },
    stage: {},
  };
}

describe("voxel scene plan", () => {
  it("builds deterministic render data without Three.js objects", () => {
    const world = makeSceneWorld();
    const first = buildVoxelScenePlan(world);
    const second = buildVoxelScenePlan(world);

    expect(second).toEqual(first);
    expect(first.blocks.length).toBeGreaterThan(30);
    expect(first.roads.length).toBeGreaterThan(0);
    expect(new Set(first.blocks.map((block) => block.id)).size).toBe(first.blocks.length);
    expect(first.blocks.every((block) => Object.values(block.size).every((size) => size > 0)))
      .toBe(true);
    expect(new Set(first.blocks.map((block) => block.geometry))).toEqual(
      new Set(["box", "cone", "cylinder", "icosphere"]),
    );
  });

  it("exposes stable location targets and dynamic agent plans for renderer interactions", () => {
    const plan = buildVoxelScenePlan(makeSceneWorld());
    const locationTargets = plan.blocks
      .map((block) => block.hitTarget)
      .filter((target) => target?.kind === "location");

    expect(locationTargets).toEqual(
      expect.arrayContaining([
        { kind: "location", id: "cafe" },
        { kind: "location", id: "park" },
      ]),
    );
    expect(plan.blocks.some((block) => block.hitTarget?.kind === "agent")).toBe(false);
    expect(plan.agents.map((agent) => agent.id)).toContain("agent-1");
    expect(plan.locationAnchors.cafe).toBeDefined();
    expect(plan.agentAnchors["agent-1"]).toBeDefined();
  });

  it("replaces ready location prefabs with an asset placement and keeps fallback data", () => {
    const plan = buildVoxelScenePlan(makeSceneWorld());

    expect(plan.assets).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          assetId: "cafe.corner",
          locationId: "cafe",
          uri: "/world/buildings/cafe-corner.glb",
        }),
        expect.objectContaining({
          assetId: "park.old-oak",
          locationId: "park",
          uri: "/world/vegetation/old-oak.glb",
        }),
      ]),
    );
    expect(plan.assets).toHaveLength(2);
    expect(plan.assets[0].fallbackBlocks.length).toBeGreaterThan(0);
    expect(plan.blocks.some((block) => block.id.startsWith("location-cafe-"))).toBe(false);
    expect(plan.blocks.some((block) => block.id.startsWith("location-park-"))).toBe(false);
  });

  it("replaces civic white boxes with the ready office and clinic assets", () => {
    const world = makeSceneWorld();
    world.locations = [
      {
        ...world.locations[0],
        id: "office",
        locationType: "office",
        visual: { visualPreset: "office" },
      },
      {
        ...world.locations[1],
        id: "hospital",
        locationType: "hospital",
        visual: { visualPreset: "clinic" },
      },
    ];
    world.agents = [];
    const plan = buildVoxelScenePlan(world);

    expect(plan.assets.map((asset) => asset.assetId)).toEqual([
      "clinic.corner",
      "office.midrise",
    ]);
    expect(plan.assets.every((asset) => asset.fallbackBlocks.length > 0)).toBe(true);
    expect(plan.blocks.some((block) => block.id.startsWith("location-office-"))).toBe(false);
    expect(plan.blocks.some((block) => block.id.startsWith("location-hospital-"))).toBe(false);
  });

  it("rounds junction paving while preserving straight road sections", () => {
    const plan = buildVoxelScenePlan(makeSceneWorld());
    const roadSurfaces = plan.blocks.filter((block) => block.id.startsWith("road-") && block.material === "road");

    expect(roadSurfaces.some((block) => block.geometry === "cylinder")).toBe(true);
    expect(roadSurfaces.some((block) => block.geometry === "box")).toBe(true);
    expect(roadSurfaces.every((block) => block.size.y <= 0.035)).toBe(true);
    expect(roadSurfaces.some((block) => block.id.startsWith("road-surface-segment"))).toBe(true);
  });

  it("uses softened plot pads and gives static residents a meaningful facing", () => {
    const plan = buildVoxelScenePlan(makeSceneWorld());
    const plotPads = plan.blocks.filter((block) => block.material === "plot");

    expect(plotPads.every((block) => block.geometry === "cylinder")).toBe(true);
    expect(plotPads.every((block) => block.size.y === 0.03)).toBe(true);
    expect(plan.agents[0].rotationY).not.toBe(0);
    expect(plan.agents[0].anchor.position.y).toBeGreaterThan(0.04);
  });

  it("builds layered perimeter terrain without raising navigable roads", () => {
    const plan = buildVoxelScenePlan(makeSceneWorld());
    const terraces = plan.blocks.filter((block) => block.id.startsWith("terrain-terrace"));
    const retainingEdges = plan.blocks.filter((block) =>
      block.id.startsWith("landscape-retaining"),
    );
    const roadSurfaces = plan.blocks.filter(
      (block) => block.id.startsWith("road-surface") && block.material === "road",
    );

    expect(terraces).toHaveLength(4);
    expect(retainingEdges).toHaveLength(4);
    expect(terraces.every((block) => block.geometry === "cylinder")).toBe(true);
    expect(Math.max(...retainingEdges.map((block) => block.size.y)))
      .toBeGreaterThanOrEqual(0.12);
    expect(terraces.every((block) => block.size.y < 0.03)).toBe(true);
    expect(plan.blocks.filter((block) => block.id.startsWith("landscape-shrub")).length)
      .toBeGreaterThanOrEqual(8);
    expect(roadSurfaces.every((block) => block.position.y < 0.06)).toBe(true);
  });

  it("gives locations a readable threshold and district-specific planting", () => {
    const plan = buildVoxelScenePlan(makeSceneWorld());
    const thresholds = plan.blocks.filter((block) => block.id.startsWith("plot-threshold"));
    const commercePlanters = plan.blocks.filter((block) =>
      block.id.startsWith("district-planter"),
    );

    expect(thresholds.map((block) => block.hitTarget?.id)).toEqual(
      expect.arrayContaining(["cafe", "park"]),
    );
    expect(thresholds.every((block) => block.size.y < 0.03)).toBe(true);
    expect(commercePlanters.length).toBeGreaterThanOrEqual(4);
  });

  it("binds activity slots to restrained, usable street furniture", () => {
    const plan = buildVoxelScenePlan(makeSceneWorld());
    const benchSeats = plan.blocks.filter((block) =>
      block.id.startsWith("activity-bench-seat"),
    );
    const conversationSurfaces = plan.blocks.filter((block) =>
      block.id.startsWith("activity-conversation-surface"),
    );
    expect(benchSeats).toHaveLength(2);
    expect(benchSeats.every((block) => block.geometry === "box")).toBe(true);
    expect(conversationSurfaces).toHaveLength(2);
    expect(plan.blocks.some((block) => block.id.startsWith("activity-work-surface")))
      .toBe(true);
    expect(plan.blocks.some((block) => block.id.startsWith("activity-tool-crate")))
      .toBe(true);
    expect(plan.blocks.filter((block) => block.id.startsWith("activity-"))
      .every((block) => block.hitTarget?.kind === "location")).toBe(true);
  });

  it("uses low hedges to give residential plots a private edge", () => {
    const world = makeSceneWorld();
    world.locations = [{
      ...world.locations[0],
      id: "home",
      locationType: "home",
      visual: { visualPreset: "home" },
    }];
    world.agents = [];
    const plan = buildVoxelScenePlan(world);
    const hedges = plan.blocks.filter((block) => block.id.startsWith("plot-hedge"));

    expect(hedges).toHaveLength(2);
    expect(hedges.every((block) => block.size.y <= 0.22)).toBe(true);
    expect(hedges.every((block) => block.hitTarget?.id === "home")).toBe(true);
    expect(plan.blocks.some((block) => block.id.startsWith("activity-mailbox"))).toBe(true);
    expect(plan.blocks.some((block) => block.id.startsWith("activity-bench"))).toBe(false);
    expect(plan.blocks.some((block) => block.id.startsWith("activity-conversation")))
      .toBe(false);
  });

  it("calculates finite bounds that contain every block", () => {
    const plan = buildVoxelScenePlan(makeSceneWorld());

    expect(Object.values(plan.bounds).every(Number.isFinite)).toBe(true);
    for (const block of plan.blocks) {
      const cos = Math.abs(Math.cos(block.rotationY));
      const sin = Math.abs(Math.sin(block.rotationY));
      const halfX = (block.size.x * cos + block.size.z * sin) / 2;
      const halfZ = (block.size.x * sin + block.size.z * cos) / 2;
      expect(block.position.x - halfX).toBeGreaterThanOrEqual(plan.bounds.minX);
      expect(block.position.x + halfX).toBeLessThanOrEqual(plan.bounds.maxX);
      expect(block.position.z - halfZ).toBeGreaterThanOrEqual(plan.bounds.minZ);
      expect(block.position.z + halfZ).toBeLessThanOrEqual(plan.bounds.maxZ);
    }
  });

  it("keeps arrival anchors stable while giving activities distinct positions", () => {
    const idleWorld = makeSceneWorld();
    const movingWorld = makeSceneWorld();
    const workingWorld = makeSceneWorld();
    idleWorld.agents[0] = { ...idleWorld.agents[0], status: "idle" };
    movingWorld.agents[0] = { ...movingWorld.agents[0], status: "moving" };
    workingWorld.agents[0] = { ...workingWorld.agents[0], status: "working" };

    const idlePlan = buildVoxelScenePlan(idleWorld);
    const movingPlan = buildVoxelScenePlan(movingWorld);
    const workingPlan = buildVoxelScenePlan(workingWorld);
    expect(idlePlan.agents[0].source.status).toBe("idle");
    expect(movingPlan.agents[0].source.status).toBe("moving");
    expect(movingPlan.agentAnchors["agent-1"]).toEqual(idlePlan.agentAnchors["agent-1"]);
    expect(workingPlan.agentAnchors["agent-1"]).not.toEqual(idlePlan.agentAnchors["agent-1"]);
  });

  it("keeps activity slots local to each status and turns conversations inward", () => {
    const mixedWorld = makeSceneWorld();
    mixedWorld.agents = [
      { ...mixedWorld.agents[0], id: "talker-1", slotIndex: 0 },
      { ...mixedWorld.agents[0], id: "worker-1", status: "working", slotIndex: 1 },
      { ...mixedWorld.agents[0], id: "talker-2", slotIndex: 2 },
    ];
    const workingWorld = makeSceneWorld();
    workingWorld.agents[0] = {
      ...workingWorld.agents[0],
      id: "worker-1",
      status: "working",
    };

    const mixedPlan = buildVoxelScenePlan(mixedWorld);
    const workingPlan = buildVoxelScenePlan(workingWorld);
    const talkers = mixedPlan.agents.filter((agent) => agent.source.status === "talking");
    const conversationCenter = {
      x: (talkers[0].anchor.position.x + talkers[1].anchor.position.x) / 2,
      z: (talkers[0].anchor.position.z + talkers[1].anchor.position.z) / 2,
    };

    expect(mixedPlan.agentAnchors["worker-1"]).toEqual(workingPlan.agentAnchors["worker-1"]);
    expect(mixedPlan.agentAnchors["talker-1"]).not.toEqual(
      mixedPlan.agentAnchors["talker-2"],
    );
    for (const talker of talkers) {
      expect(talker.rotationY).toBeCloseTo(
        Math.atan2(
          conversationCenter.x - talker.anchor.position.x,
          conversationCenter.z - talker.anchor.position.z,
        ),
      );
    }
  });
});
