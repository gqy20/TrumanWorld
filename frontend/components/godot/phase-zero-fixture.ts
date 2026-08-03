import type { GodotWorldSnapshot } from "./protocol";

export const PHASE_ZERO_RUN_ID = "phase-zero";

export const PHASE_ZERO_WORLD_SNAPSHOT: GodotWorldSnapshot = {
  map_id: "campus-world-v2",
  map_content_hash: "sha256:e2a7e49020876c2fea7ec0850ba58ff955bd67a85a944835bffb02cffbc532da",
  tick: 12,
  world_time: "2026-08-03T09:00:00Z",
  run_status: "running",
  simulation_speed: 1,
  agents: [
    {
      id: "mei",
      name: "Mei",
      position_meters: [-3, 0, -1.2],
      facing_radians: 0.3,
      activity: { activity_type: "idle", status: "performing", progress: 0.4 },
    },
    {
      id: "chen",
      name: "Chen",
      position_meters: [0, 0, 1.4],
      facing_radians: -0.8,
      activity: { activity_type: "talk", status: "performing", progress: 0.2 },
    },
    {
      id: "lin",
      name: "Lin",
      position_meters: [3.2, 0, -0.5],
      facing_radians: 2.4,
      activity: { activity_type: "walk", status: "navigating", progress: 0.65 },
    },
  ],
  object_states: [],
  conversations: [],
};
