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
      position_meters: [6.55, 0, -0.45],
      facing_radians: 0.3,
      activity: {
        activity_type: "drink_coffee",
        status: "performing",
        progress: 0.64,
        current_step_id: "drink",
        current_action: "drink",
        visual_state: "drink",
        zone_id: "cafe.seating",
        claimed_resource_ids: ["slot:cafe:window-chair-1:sit"],
      },
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
      position_meters: [1.25, 0, 1.2],
      facing_radians: 2.4,
      activity: { activity_type: "talk", status: "paused", progress: 0.65 },
    },
  ],
  object_states: [
    {
      resource_id: "slot:cafe:window-chair-1:sit",
      object_id: "cafe.window-chair-1",
      object_type: "cafe_chair",
      slot_kind: "sit",
      occupant_agent_ids: ["mei"],
      queue_agent_ids: [],
    },
  ],
  conversations: [
    {
      id: "fixture-conversation",
      participant_ids: ["chen", "lin"],
      participant_names: ["Chen", "Lin"],
      active_speaker_id: "chen",
      active_speaker_name: "Chen",
      last_message: "Morning. Are you heading to class?",
      turn_count: 2,
      phase: "open",
    },
  ],
};
