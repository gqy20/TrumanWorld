import type { SceneWorld } from "@/lib/world-scene-adapter";

import { buildVoxelScenePlan } from "../scene-plan";

function makeSceneWorld(): SceneWorld {
  return {
    runId: "run-1",
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
    expect(first.blocks.length).toBeGreaterThan(350);
    expect(new Set(first.blocks.map((block) => block.id)).size).toBe(first.blocks.length);
    expect(first.blocks.every((block) => Object.values(block.size).every((size) => size > 0)))
      .toBe(true);
  });

  it("exposes stable location and agent targets for renderer interactions", () => {
    const plan = buildVoxelScenePlan(makeSceneWorld());
    const locationTargets = plan.blocks
      .map((block) => block.hitTarget)
      .filter((target) => target?.kind === "location");
    const agentTargets = plan.blocks
      .map((block) => block.hitTarget)
      .filter((target) => target?.kind === "agent");

    expect(locationTargets).toEqual(
      expect.arrayContaining([
        { kind: "location", id: "cafe" },
        { kind: "location", id: "park" },
      ]),
    );
    expect(agentTargets).toContainEqual({ kind: "agent", id: "agent-1" });
    expect(plan.locationAnchors.cafe).toBeDefined();
    expect(plan.agentAnchors["agent-1"]).toBeDefined();
  });

  it("calculates finite bounds that contain every block", () => {
    const plan = buildVoxelScenePlan(makeSceneWorld());

    expect(Object.values(plan.bounds).every(Number.isFinite)).toBe(true);
    for (const block of plan.blocks) {
      expect(block.position.x - block.size.x / 2).toBeGreaterThanOrEqual(plan.bounds.minX);
      expect(block.position.x + block.size.x / 2).toBeLessThanOrEqual(plan.bounds.maxX);
      expect(block.position.z - block.size.z / 2).toBeGreaterThanOrEqual(plan.bounds.minZ);
      expect(block.position.z + block.size.z / 2).toBeLessThanOrEqual(plan.bounds.maxZ);
    }
  });

  it("maps agent status changes to render materials without moving its anchor", () => {
    const talkingWorld = makeSceneWorld();
    const movingWorld = makeSceneWorld();
    movingWorld.agents[0] = { ...movingWorld.agents[0], status: "moving" };

    const talkingPlan = buildVoxelScenePlan(talkingWorld);
    const movingPlan = buildVoxelScenePlan(movingWorld);
    const talkingBody = talkingPlan.blocks.find((block) => block.id.startsWith("agent-agent-1"));
    const movingBody = movingPlan.blocks.find((block) => block.id.startsWith("agent-agent-1"));

    expect(talkingBody?.material).toBe("agentTalking");
    expect(movingBody?.material).toBe("agentMoving");
    expect(movingPlan.agentAnchors["agent-1"]).toEqual(talkingPlan.agentAnchors["agent-1"]);
  });
});
