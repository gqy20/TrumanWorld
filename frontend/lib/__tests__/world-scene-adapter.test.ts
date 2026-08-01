import { makeWorldSnapshot } from "@/test-utils/app/fixtures";

import { buildSceneWorld } from "../world-scene-adapter";

describe("buildSceneWorld", () => {
  it("restores an in-transit agent and its path from the authoritative snapshot", () => {
    const base = makeWorldSnapshot();
    const world = makeWorldSnapshot({
      run: { ...base.run, current_tick: 3 },
      agents: [
        {
          id: "agent-1",
          name: "Mei Lin",
          occupation: "Student",
          current_location_id: null,
          movement: {
            id: "movement-agent-1",
            state: "in_transit",
            from_location_id: "cafe",
            to_location_id: "library",
            started_tick: 2,
            arrival_tick: 4,
          },
        },
      ],
      locations: base.locations.map((location) => ({ ...location, occupants: [] })),
      recent_events: [],
    });

    const scene = buildSceneWorld(world);

    expect(scene.agents).toEqual([
      expect.objectContaining({
        id: "agent-1",
        locationId: "cafe",
        movementId: "movement-agent-1",
        status: "moving",
      }),
    ]);
    expect(scene.activeMovements).toEqual([
      expect.objectContaining({
        id: "movement-agent-1",
        actorId: "agent-1",
        fromLocationId: "cafe",
        toLocationId: "library",
        initialProgress: 0.5,
        isActive: true,
      }),
    ]);
  });

  it("keeps the location occupant fallback for older snapshots", () => {
    const scene = buildSceneWorld(makeWorldSnapshot());

    expect(scene.agents.map((agent) => agent.id)).toEqual(["agent-1"]);
    expect(scene.activeMovements).toEqual([]);
  });

  it("exposes whether movement animation may advance", () => {
    const base = makeWorldSnapshot();

    expect(buildSceneWorld(base).isRunning).toBe(true);
    expect(
      buildSceneWorld({ ...base, run: { ...base.run, status: "paused" } }).isRunning,
    ).toBe(false);
  });

  it("exposes canonical time data for the renderer lighting system", () => {
    const base = makeWorldSnapshot();
    const scene = buildSceneWorld({
      ...base,
      world_clock: { ...base.world_clock!, hour: 19, time: "19:00" },
    });

    expect(scene.ambience).toEqual(expect.objectContaining({ hour: 19, timeOfDay: "evening" }));
  });
});
