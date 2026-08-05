import type { WorldSnapshot } from "@/lib/types";

import type {
  GodotAgentSnapshot,
  GodotConversationSnapshot,
  GodotWorldSnapshot,
} from "./protocol";

export function toGodotWorldSnapshot(world: WorldSnapshot): GodotWorldSnapshot | null {
  if (!world.map_id || !world.map_content_hash) return null;

  const locations = new Map(world.locations.map((location) => [location.id, location]));
  const agents = (world.agents ?? []).map<GodotAgentSnapshot>((agent) => {
    const location = agent.current_location_id
      ? locations.get(agent.current_location_id)
      : undefined;
    const fallbackPosition: [number, number, number] = [
      location?.x ?? 0,
      0,
      location?.y ?? 0,
    ];

    return {
      id: agent.id,
      name: agent.name,
      config_id: agent.config_id ?? null,
      visual_asset_id: agent.visual_asset_id ?? null,
      position_meters: agent.position_meters ?? fallbackPosition,
      facing_radians: agent.facing_radians ?? 0,
      zone_id: agent.zone_id ?? null,
      movement: agent.movement ? { ...agent.movement } : null,
      activity: agent.activity
        ? {
            activity_type: agent.activity.activity_type,
            status: agent.activity.status,
            progress: agent.activity.progress ?? 0,
            elapsed_seconds: agent.activity.elapsed_seconds,
            current_step_id: agent.activity.current_step_id,
            current_action: agent.activity.current_action,
            visual_state: agent.activity.visual_state,
            zone_id: agent.activity.zone_id,
            queue_position: agent.activity.queue_position,
            claimed_resource_ids: agent.activity.claimed_resource_ids,
            paused_at_world_time: agent.activity.paused_at_world_time,
            pause_reason: agent.activity.pause_reason,
            paused_for_encounter_id: agent.activity.paused_for_encounter_id,
            paused_for_conversation_id: agent.activity.paused_for_conversation_id,
            resume_status: agent.activity.resume_status,
            paused_position_meters: agent.activity.paused_position_meters,
          }
        : null,
    };
  });

  return {
    map_id: world.map_id,
    map_content_hash: world.map_content_hash,
    tick: world.tick ?? world.run.current_tick ?? 0,
    world_time: world.world_time ?? world.world_clock?.iso ?? new Date(0).toISOString(),
    run_status: world.run_status ?? world.run.status,
    simulation_speed: world.simulation_speed ?? 1,
    scenario_id: world.scenario_id ?? world.run.scenario_type ?? null,
    agents,
    object_states: world.object_states ?? [],
    conversations: (world.conversations ?? []).filter(isGodotConversation),
  };
}

function isGodotConversation(
  value: Record<string, unknown>,
): value is GodotConversationSnapshot & Record<string, unknown> {
  return (
    typeof value.id === "string" &&
    Array.isArray(value.participant_ids) &&
    value.participant_ids.every((participantId) => typeof participantId === "string")
  );
}
