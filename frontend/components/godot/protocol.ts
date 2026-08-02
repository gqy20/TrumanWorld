export const GODOT_PROTOCOL_VERSION = 1 as const;

export const GODOT_HOST_MESSAGE_TYPES = [
  "initialize",
  "world_snapshot",
  "world_event_batch",
  "run_status_changed",
  "simulation_speed_changed",
  "focus_entity",
  "set_quality",
  "dispose",
] as const;

export const GODOT_CLIENT_MESSAGE_TYPES = [
  "ready",
  "selection_changed",
  "inspect_requested",
  "camera_changed",
  "visual_action_completed",
  "client_metric_batch",
  "client_error",
  "snapshot_required",
] as const;

export type GodotHostMessageType = (typeof GODOT_HOST_MESSAGE_TYPES)[number];
export type GodotClientMessageType = (typeof GODOT_CLIENT_MESSAGE_TYPES)[number];

export type GodotEnvelope<TType extends string = string, TPayload = Record<string, unknown>> = {
  protocol_version: typeof GODOT_PROTOCOL_VERSION;
  message_id: string;
  run_id: string;
  sequence: number;
  sent_at: string;
  type: TType;
  payload: TPayload;
};

export type GodotAgentSnapshot = {
  id: string;
  name: string;
  position_meters: [number, number, number];
  facing_radians: number;
  zone_id?: string | null;
  movement?: Record<string, unknown> | null;
  activity?: {
    activity_type: string;
    status: string;
    progress: number;
  } | null;
};

export type GodotWorldSnapshot = {
  map_id: string;
  map_content_hash: string;
  tick: number;
  world_time: string;
  run_status: string;
  simulation_speed: number;
  agents: GodotAgentSnapshot[];
  object_states: Array<Record<string, unknown>>;
  conversations: Array<Record<string, unknown>>;
};

export type GodotSelectionPayload = {
  kind: "agent" | "location" | "object";
  id: string;
};

export type GodotDecodeResult =
  | { ok: true; envelope: GodotEnvelope<GodotClientMessageType> }
  | { ok: false; error: string };

export function createGodotEnvelope<TType extends GodotHostMessageType>(
  type: TType,
  runId: string,
  sequence: number,
  payload: Record<string, unknown>,
): GodotEnvelope<TType> {
  return {
    protocol_version: GODOT_PROTOCOL_VERSION,
    message_id: `host-${sequence}-${createMessageSuffix()}`,
    run_id: runId,
    sequence,
    sent_at: new Date().toISOString(),
    type,
    payload,
  };
}

export function decodeGodotClientMessage(value: unknown): GodotDecodeResult {
  let parsed: unknown = value;
  if (typeof value === "string") {
    try {
      parsed = JSON.parse(value);
    } catch {
      return { ok: false, error: "invalid_json" };
    }
  }

  if (!isRecord(parsed)) return { ok: false, error: "invalid_envelope" };
  if (parsed.protocol_version !== GODOT_PROTOCOL_VERSION) {
    return { ok: false, error: "protocol_mismatch" };
  }
  if (
    typeof parsed.type !== "string" ||
    !GODOT_CLIENT_MESSAGE_TYPES.includes(parsed.type as GodotClientMessageType)
  ) {
    return { ok: false, error: "unknown_type" };
  }
  if (typeof parsed.run_id !== "string") return { ok: false, error: "invalid_run_id" };
  if (!Number.isSafeInteger(parsed.sequence) || Number(parsed.sequence) < 0) {
    return { ok: false, error: "invalid_sequence" };
  }
  if (!isRecord(parsed.payload)) return { ok: false, error: "invalid_payload" };
  if (typeof parsed.message_id !== "string" || typeof parsed.sent_at !== "string") {
    return { ok: false, error: "invalid_metadata" };
  }

  return {
    ok: true,
    envelope: parsed as GodotEnvelope<GodotClientMessageType>,
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function createMessageSuffix(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}
