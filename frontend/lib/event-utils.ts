import {
  DIRECTOR_EVENT_ACTIVITY,
  DIRECTOR_EVENT_BROADCAST,
  EVENT_CONVERSATION_JOINED,
  EVENT_CONVERSATION_STARTED,
  DIRECTOR_EVENT_INJECT,
  DIRECTOR_EVENT_SHUTDOWN,
  DIRECTOR_EVENT_WEATHER_CHANGE,
  EVENT_LISTEN,
  EVENT_MOVE,
  EVENT_PLAN,
  EVENT_REFLECT,
  EVENT_REST,
  EVENT_SPEECH,
  EVENT_TALK,
  EVENT_WORK,
  isDirectorEventType,
  type EventType,
} from "@/lib/simulation-protocol";
import type { AgentDetails, TimelineEvent, WorldEvent } from "@/lib/types";

type EventMeta = {
  icon: string;
  label: string;
  chip: string;
  color: string;
};

function looksLikeOpaqueAgentId(value: string): boolean {
  return /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i.test(value);
}

function resolveSpeakerLabel(
  speakerName: unknown,
  speakerAgentId: unknown,
  fallback: unknown,
  nameMap?: Record<string, string>,
): string {
  if (typeof speakerName === "string" && speakerName.trim().length > 0) {
    return speakerName;
  }

  if (typeof speakerAgentId === "string" && speakerAgentId.trim().length > 0) {
    if (nameMap && nameMap[speakerAgentId]) {
      return nameMap[speakerAgentId];
    }
    if (!looksLikeOpaqueAgentId(speakerAgentId)) {
      return speakerAgentId;
    }
  }

  if (typeof fallback === "string" && fallback.trim().length > 0) {
    return fallback;
  }

  return "某人";
}

const DEFAULT_EVENT_META: EventMeta = {
  icon: "✨",
  label: "未知事件",
  chip: "bg-slate-50 text-slate-700 border border-slate-100",
  color: "#6b7280",
};

export const EVENT_META: Partial<Record<EventType, EventMeta>> = {
  [EVENT_SPEECH]: {
    icon: "💬",
    label: "发言",
    chip: "bg-rose-50 text-rose-700 border border-rose-100",
    color: "#ec4899",
  },
  [EVENT_LISTEN]: {
    icon: "👂",
    label: "倾听",
    chip: "bg-fuchsia-50 text-fuchsia-700 border border-fuchsia-100",
    color: "#c026d3",
  },
  [EVENT_CONVERSATION_STARTED]: {
    icon: "🫱",
    label: "对话开始",
    chip: "bg-sky-50 text-sky-700 border border-sky-100",
    color: "#0ea5e9",
  },
  [EVENT_CONVERSATION_JOINED]: {
    icon: "➕",
    label: "加入对话",
    chip: "bg-teal-50 text-teal-700 border border-teal-100",
    color: "#0f766e",
  },
  [EVENT_TALK]: {
    icon: "💬",
    label: "发言",
    chip: "bg-rose-50 text-rose-700 border border-rose-100",
    color: "#ec4899",
  },
  [EVENT_MOVE]: {
    icon: "🚶",
    label: "移动",
    chip: "bg-emerald-50 text-emerald-700 border border-emerald-100",
    color: "#10b981",
  },
  [EVENT_WORK]: {
    icon: "⚒️",
    label: "工作",
    chip: "bg-amber-50 text-amber-700 border border-amber-100",
    color: "#f59e0b",
  },
  [EVENT_REST]: {
    icon: "😴",
    label: "休息",
    chip: "bg-indigo-50 text-indigo-700 border border-indigo-100",
    color: "#6366f1",
  },
  [DIRECTOR_EVENT_INJECT]: {
    icon: "📢",
    label: "导演注入",
    chip: "bg-red-50 text-red-700 border border-red-100",
    color: "#dc2626",
  },
  [DIRECTOR_EVENT_BROADCAST]: {
    icon: "📢",
    label: "导演广播",
    chip: "bg-red-50 text-red-700 border border-red-100",
    color: "#dc2626",
  },
  [DIRECTOR_EVENT_ACTIVITY]: {
    icon: "🎭",
    label: "导演活动",
    chip: "bg-red-50 text-red-700 border border-red-100",
    color: "#dc2626",
  },
  [DIRECTOR_EVENT_SHUTDOWN]: {
    icon: "⛔",
    label: "导演关闭",
    chip: "bg-red-50 text-red-700 border border-red-100",
    color: "#dc2626",
  },
  [DIRECTOR_EVENT_WEATHER_CHANGE]: {
    icon: "🌦️",
    label: "导演天气",
    chip: "bg-red-50 text-red-700 border border-red-100",
    color: "#dc2626",
  },
  [EVENT_PLAN]: {
    icon: "📋",
    label: "计划",
    chip: "bg-violet-50 text-violet-700 border border-violet-100",
    color: "#8b5cf6",
  },
  [EVENT_REFLECT]: {
    icon: "🔍",
    label: "反思",
    chip: "bg-cyan-50 text-cyan-700 border border-cyan-100",
    color: "#06b6d4",
  },
};

export function getEventMeta(eventType: EventType): EventMeta {
  return EVENT_META[eventType] ?? { ...DEFAULT_EVENT_META, label: eventType };
}

export function describeWorldEvent(
  event: WorldEvent,
  nameMap: Record<string, string>,
  locationMap: Record<string, string>,
): string {
  const actor = nameMap[event.actor_agent_id ?? ""] || event.actor_agent_id || "有人";
  const target = nameMap[event.target_agent_id ?? ""] || event.target_agent_id || "某人";
  const atPlace = locationMap[event.location_id ?? ""] || event.location_id || "小镇";
  const toPlace =
    locationMap[String(event.payload.to_location_id ?? "")] || String(event.payload.to_location_id || atPlace);

  switch (event.event_type) {
    case EVENT_MOVE:
      return `${actor} 前往了 ${toPlace}`;
    case EVENT_SPEECH:
    case EVENT_TALK:
      return `${actor} 对 ${target} 发言`;
    case EVENT_LISTEN: {
      const speaker = resolveSpeakerLabel(
        event.payload.speaker_name,
        event.payload.speaker_agent_id,
        target,
        nameMap,
      );
      return `${actor} 正在听 ${speaker} 说话`;
    }
    case EVENT_CONVERSATION_STARTED:
      return `${actor} 与 ${target} 开始了一段对话`;
    case EVENT_CONVERSATION_JOINED: {
      const speaker = resolveSpeakerLabel(
        event.payload.speaker_name,
        event.payload.speaker_agent_id,
        target,
        nameMap,
      );
      return `${actor} 加入了 ${speaker} 主导的对话`;
    }
    case EVENT_WORK:
      return `${actor} 在 ${atPlace} 专心工作`;
    case EVENT_REST:
      return `${actor} 在 ${atPlace} 休息`;
    case DIRECTOR_EVENT_INJECT:
    case DIRECTOR_EVENT_BROADCAST:
    case DIRECTOR_EVENT_ACTIVITY:
    case DIRECTOR_EVENT_SHUTDOWN:
    case DIRECTOR_EVENT_WEATHER_CHANGE:
      return `导演播报：${String(event.payload.message || "发生了一件大事")}`;
    case EVENT_PLAN:
      return `${actor} 制定了新的计划`;
    case EVENT_REFLECT:
      return `${actor} 陷入了沉思`;
    default:
      return `${atPlace} 发生了一些事情`;
  }
}

export function describeTimelineEvent(event: Pick<TimelineEvent, "event_type" | "payload">) {
  const payload = event.payload;

  if (event.event_type === EVENT_SPEECH || event.event_type === EVENT_TALK) {
    const msg = payload.message ? `：「${String(payload.message)}」` : "";
    const actor = String(payload.actor_name ?? payload.actor_agent_id ?? "某人");
    const target = String(payload.target_name ?? payload.target_agent_id ?? "某人");
    return `${actor} 对 ${target} 发言${msg}`;
  }
  if (event.event_type === EVENT_LISTEN) {
    const actor = String(payload.actor_name ?? payload.actor_agent_id ?? "某人");
    const speaker = resolveSpeakerLabel(payload.speaker_name, payload.speaker_agent_id, payload.target_name);
    return `${actor} 正在倾听 ${speaker}`;
  }
  if (event.event_type === EVENT_CONVERSATION_STARTED) {
    const actor = String(payload.actor_name ?? payload.actor_agent_id ?? "某人");
    const target = String(payload.target_name ?? payload.target_agent_id ?? "某人");
    return `${actor} 和 ${target} 开始了一段对话`;
  }
  if (event.event_type === EVENT_CONVERSATION_JOINED) {
    const actor = String(payload.actor_name ?? payload.actor_agent_id ?? "某人");
    const speaker = resolveSpeakerLabel(payload.speaker_name, payload.speaker_agent_id, payload.target_name);
    return `${actor} 加入了 ${speaker} 主导的对话`;
  }
  if (event.event_type === EVENT_MOVE) {
    const actor = String(payload.actor_name ?? payload.actor_agent_id ?? "某人");
    const to = String(payload.to_location_name ?? payload.to_location_id ?? "某地");
    return `${actor} 前往了 ${to}`;
  }
  if (event.event_type === EVENT_WORK) {
    const actor = String(payload.actor_name ?? payload.actor_agent_id ?? "某人");
    return `${actor} 专心工作中`;
  }
  if (event.event_type === EVENT_REST) {
    const actor = String(payload.actor_name ?? payload.actor_agent_id ?? "某人");
    return `${actor} 暂时休息`;
  }
  if (isDirectorEventType(event.event_type)) {
    return `导演播报：${String(payload.message ?? "发生了一件大事")}`;
  }
  if (event.event_type === EVENT_PLAN) {
    const actor = String(payload.actor_name ?? payload.actor_agent_id ?? "某人");
    return `${actor} 制定了今日计划`;
  }
  if (event.event_type === EVENT_REFLECT) {
    const actor = String(payload.actor_name ?? payload.actor_agent_id ?? "某人");
    return `${actor} 进行了深度反思`;
  }

  return event.event_type;
}

export function describeAgentEvent(event: AgentDetails["recent_events"][number]) {
  if ((event.event_type === EVENT_SPEECH || event.event_type === EVENT_TALK) && event.target_name) {
    return `对 ${event.target_name} 发言`;
  }
  if (event.event_type === EVENT_LISTEN) {
    return `正在倾听 ${resolveSpeakerLabel(event.payload.speaker_name, event.payload.speaker_agent_id, event.target_name)}`;
  }
  if (event.event_type === EVENT_CONVERSATION_STARTED && event.target_name) {
    return `与 ${event.target_name} 开始对话`;
  }
  if (event.event_type === EVENT_CONVERSATION_JOINED) {
    return `加入了一段对话`;
  }
  if (event.event_type === EVENT_MOVE && event.location_name) {
    return `前往 ${event.location_name}`;
  }
  if (event.event_type === EVENT_WORK && event.location_name) {
    return `在 ${event.location_name} 工作`;
  }
  if (event.event_type === EVENT_REST && event.location_name) {
    return `在 ${event.location_name} 休息`;
  }
  if (isDirectorEventType(event.event_type)) {
    return `收到导演消息：${String(event.payload.message ?? event.event_type)}`;
  }

  return event.event_type;
}
