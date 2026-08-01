import { makeWorldSnapshot } from "@/test-utils/app/fixtures";
import { buildSceneWorld, type SceneBubble, type SceneMoveTrail } from "@/lib/world-scene-adapter";

import { buildVoxelEventPlan, findRoadPath } from "../event-plan";
import { snapRoadPoint } from "../road-graph";
import { buildVoxelScenePlan } from "../scene-plan";

describe("voxel event plan", () => {
  it("anchors speech to the speaker and maps movement onto the road graph", () => {
    const world = buildSceneWorld(makeWorldSnapshot());
    const scenePlan = buildVoxelScenePlan(world);
    const eventPlan = buildVoxelEventPlan(world.bubbles, world.moveTrails, scenePlan);

    expect(eventPlan.bubbles).toHaveLength(1);
    expect(eventPlan.bubbles[0]).toMatchObject({
      id: "event-1",
      speakerAgentId: "agent-1",
      position: {
        x: scenePlan.agentAnchors["agent-1"].position.x,
        y: 1.18,
        z: scenePlan.agentAnchors["agent-1"].position.z,
      },
    });

    const trail = eventPlan.moveTrails[0];
    const fromPlot = scenePlan.plots.find((plotItem) => plotItem.locationId === "library");
    const toPlot = scenePlan.plots.find((plotItem) => plotItem.locationId === "cafe");
    const roadKeys = new Set(scenePlan.roads.map((road) => `${road.x}:${road.z}`));

    expect(trail.id).toBe("event-2");
    expect(trail.points[0]).toMatchObject(fromPlot!.agentAnchors[0]);
    expect(trail.points.at(-1)).toEqual({
      ...scenePlan.agentAnchors["agent-1"].position,
      y: 0,
    });
    expect(trail.points.slice(2, -2).every((point) => roadKeys.has(`${point.x}:${point.z}`)))
      .toBe(true);
    expect(trail.points.every((point) => point.y === 0)).toBe(true);
    expect(trail.points).toContainEqual({ ...snapRoadPoint(fromPlot!.entrance), y: 0 });
    expect(trail.points).toContainEqual({ ...snapRoadPoint(toPlot!.entrance), y: 0 });
    expect(trail.points.slice(1, -1).map(({ x, z }) => ({ x, z }))).toEqual(
      [4, 3, 2, 1, 0].map((x) => ({ x: x - 2, z: 0 })),
    );
  });

  it("falls back to a location roof anchor when the speaker is not present", () => {
    const world = buildSceneWorld(makeWorldSnapshot());
    const scenePlan = buildVoxelScenePlan(world);
    const bubble: SceneBubble = {
      id: "remote-speech",
      text: "The library is closing soon",
      speakerAgentId: "agent-not-on-stage",
      speakerName: "Librarian",
      locationId: "library",
      recencyIndex: 0,
    };

    const eventPlan = buildVoxelEventPlan([bubble], [], scenePlan);

    expect(eventPlan.bubbles[0].position.x).toBe(scenePlan.locationAnchors.library.position.x);
    expect(eventPlan.bubbles[0].position.z).toBe(scenePlan.locationAnchors.library.position.z);
    expect(eventPlan.bubbles[0].position.y).toBeGreaterThan(1);
  });

  it("drops events whose anchors cannot be resolved", () => {
    const world = buildSceneWorld(makeWorldSnapshot());
    const scenePlan = buildVoxelScenePlan(world);
    const bubble: SceneBubble = {
      id: "missing-bubble",
      text: "Hello",
      speakerName: "Unknown",
      locationId: "missing",
      recencyIndex: 0,
    };
    const trail: SceneMoveTrail = {
      id: "missing-trail",
      actorName: "Unknown",
      fromLocationId: "missing",
      toLocationId: "cafe",
      recencyIndex: 0,
    };

    expect(buildVoxelEventPlan([bubble], [trail], scenePlan)).toEqual({
      bubbles: [],
      moveTrails: [],
    });
    expect(findRoadPath(scenePlan.roads, { x: 999, z: 999 }, { x: 0, z: 0 })).toEqual([]);
  });
});
