import { makeWorldSnapshot } from "@/test-utils/app/fixtures";

import { toGodotWorldSnapshot } from "../world-snapshot-adapter";

describe("toGodotWorldSnapshot", () => {
  test("projects the shared world snapshot onto the Godot protocol", () => {
    const result = toGodotWorldSnapshot(makeWorldSnapshot());

    expect(result).toMatchObject({
      map_id: "narrative-world-v1",
      map_content_hash: "sha256:narrative-world-test",
      tick: 24,
      world_time: "2026-03-02T08:00:00Z",
      run_status: "running",
      scenario_id: "narrative_world",
    });
    expect(result?.agents[0]).toMatchObject({
      id: "agent-1",
      position_meters: [10, 0, 20],
      facing_radians: 0,
    });
  });

  test("falls back to the semantic location when an agent lacks a meter position", () => {
    const world = makeWorldSnapshot();
    const agent = world.locations[0].occupants[0];
    if (!agent) throw new Error("fixture agent is required");
    agent.position_meters = null;
    world.agents = [agent];

    expect(toGodotWorldSnapshot(world)?.agents[0].position_meters).toEqual([10, 0, 20]);
  });

  test("rejects scenarios without an exported Godot map contract", () => {
    const world = makeWorldSnapshot({ map_id: null });

    expect(toGodotWorldSnapshot(world)).toBeNull();
  });
});
