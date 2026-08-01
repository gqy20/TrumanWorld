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

  it("rounds junction paving while preserving straight road sections", () => {
    const plan = buildVoxelScenePlan(makeSceneWorld());
    const roadSurfaces = plan.blocks.filter((block) => block.id.startsWith("road-") && block.material === "road");

    expect(roadSurfaces.some((block) => block.geometry === "cylinder")).toBe(true);
    expect(roadSurfaces.some((block) => block.geometry === "box")).toBe(true);
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

  it("keeps an agent anchor stable when its dynamic status changes", () => {
    const talkingWorld = makeSceneWorld();
    const movingWorld = makeSceneWorld();
    movingWorld.agents[0] = { ...movingWorld.agents[0], status: "moving" };

    const talkingPlan = buildVoxelScenePlan(talkingWorld);
    const movingPlan = buildVoxelScenePlan(movingWorld);
    expect(talkingPlan.agents[0].source.status).toBe("talking");
    expect(movingPlan.agents[0].source.status).toBe("moving");
    expect(movingPlan.agentAnchors["agent-1"]).toEqual(talkingPlan.agentAnchors["agent-1"]);
  });
});
