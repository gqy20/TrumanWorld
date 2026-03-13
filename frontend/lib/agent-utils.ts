import {
  EVENT_CONVERSATION_JOINED,
  EVENT_CONVERSATION_STARTED,
  EVENT_LISTEN,
  EVENT_MOVE,
  EVENT_REST,
  EVENT_SPEECH,
  EVENT_TALK,
  EVENT_WORK,
  type EventType,
} from "@/lib/simulation-protocol";

export type AgentStatus = "idle" | "working" | "talking" | "moving" | "resting";

export function inferAgentStatus(
  agentId: string,
  recentEvents: Array<{ actor_agent_id?: string; target_agent_id?: string; event_type: EventType }>
): AgentStatus {
  const relevantEvents = recentEvents.filter(
    (e) => e.actor_agent_id === agentId || e.target_agent_id === agentId
  );

  if (relevantEvents.length === 0) return "idle";

  const latest = relevantEvents[0];
  switch (latest.event_type) {
    case EVENT_SPEECH:
    case EVENT_LISTEN:
    case EVENT_CONVERSATION_STARTED:
    case EVENT_CONVERSATION_JOINED:
    case EVENT_TALK:
      return "talking";
    case EVENT_WORK:
      return "working";
    case EVENT_MOVE:
      return "moving";
    case EVENT_REST:
      return "resting";
    default:
      return "idle";
  }
}

export function relationshipTone(value: number) {
  if (value >= 0.75) return "bg-emerald-500";
  if (value >= 0.45) return "bg-amber-400";
  return "bg-slate-300";
}

export function formatAgentScore(value?: number | null): string {
  if (value == null || Number.isNaN(value)) return "0.00";
  return value.toFixed(2);
}

export function formatMemoryCategory(category?: string | null): string {
  switch (category) {
    case "long_term":
      return "长期";
    case "medium_term":
      return "中期";
    case "short_term":
      return "短期";
    default:
      return category || "未知";
  }
}

export function memoryCategoryBadgeClass(category?: string | null): string {
  switch (category) {
    case "long_term":
      return "border-emerald-200 bg-emerald-50 text-emerald-700";
    case "medium_term":
      return "border-amber-200 bg-amber-50 text-amber-700";
    case "short_term":
      return "border-slate-200 bg-white text-slate-500";
    default:
      return "border-slate-200 bg-white text-slate-500";
  }
}
