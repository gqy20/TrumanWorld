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
} from "@/lib/simulation-protocol";
import type { WorldEvent, WorldSnapshot } from "@/lib/types";
export type LocationBeat = "conversation" | "arrival" | "working" | "resting" | "quiet";
export type EventFilter = "all" | "social" | "activity" | "movement";

function isConversationStructureEvent(event: WorldEvent): boolean {
  return (
    event.event_type === EVENT_CONVERSATION_STARTED ||
    event.event_type === EVENT_CONVERSATION_JOINED
  );
}

function isConversationSpeechEvent(event: WorldEvent): boolean {
  return event.event_type === EVENT_TALK || event.event_type === EVENT_SPEECH;
}

export function isSocialEvent(event: WorldEvent): boolean {
  return (
    event.event_type === EVENT_TALK ||
    event.event_type === EVENT_SPEECH ||
    event.event_type === EVENT_LISTEN ||
    event.event_type === EVENT_CONVERSATION_STARTED ||
    event.event_type === EVENT_CONVERSATION_JOINED
  );
}

export function buildWorldNameMaps(world: WorldSnapshot) {
  const agentNameMap: Record<string, string> = {};
  const locationNameMap: Record<string, string> = {};

  for (const location of world.locations) {
    locationNameMap[location.id] = location.name;
    for (const agent of location.occupants) {
      agentNameMap[agent.id] = agent.name;
    }
  }

  return { agentNameMap, locationNameMap };
}

export function filterWorldEvents(
  events: WorldEvent[],
  eventFilter: EventFilter,
  locationFilter: string | null = null,
) {
  return events
    .filter((event) => eventMatchesFilter(event, eventFilter))
    .filter((event) => locationFilter === null || event.location_id === locationFilter);
}

export function compressConversationDisplayEvents(events: WorldEvent[]): WorldEvent[] {
  const conversationIdsWithSpeech = new Set<string>();

  for (const event of events) {
    const conversationId = String(event.payload.conversation_id ?? "");
    if (!conversationId) continue;
    if (isConversationSpeechEvent(event)) {
      conversationIdsWithSpeech.add(conversationId);
    }
  }

  return events.filter((event) => {
    if (!isConversationStructureEvent(event)) return true;
    const conversationId = String(event.payload.conversation_id ?? "");
    if (!conversationId) return true;
    return !conversationIdsWithSpeech.has(conversationId);
  });
}

export function isAgentSociallyEngaged(
  agentId: string,
  currentGoal: string | undefined,
  recentEvents: WorldEvent[],
  currentTick?: number,
): boolean {
  if (currentGoal === "talk") {
    return true;
  }

  return recentEvents.some((event) => {
    if (!isSocialEvent(event)) return false;
    if (currentTick !== undefined && event.tick_no < currentTick - 1) return false;
    return event.actor_agent_id === agentId || event.target_agent_id === agentId;
  });
}

export function getLocationHeadlineEvents(
  locationId: string,
  events: WorldEvent[],
  limit: number = 2,
): WorldEvent[] {
  const locationEvents = compressConversationDisplayEvents(
    events.filter((event) => event.location_id === locationId),
  );

  const ranked = [...locationEvents].sort((left, right) => {
    if (right.tick_no !== left.tick_no) return right.tick_no - left.tick_no;
    const leftSocial = isSocialEvent(left) ? 1 : 0;
    const rightSocial = isSocialEvent(right) ? 1 : 0;
    return rightSocial - leftSocial;
  });

  return ranked.slice(0, limit);
}

export function locationTone(locationType: string) {
  if (locationType === "cafe") return "border-amber-200 bg-amber-50 text-amber-900";
  if (locationType === "plaza") return "border-sky-200 bg-sky-50 text-sky-900";
  if (locationType === "park") return "border-emerald-200 bg-emerald-50 text-emerald-900";
  if (locationType === "shop") return "border-violet-200 bg-violet-50 text-violet-900";
  if (locationType === "home") return "border-pink-200 bg-pink-50 text-pink-900";
  if (locationType === "office") return "border-sky-200 bg-sky-50 text-sky-900";
  if (locationType === "hospital") return "border-rose-200 bg-rose-50 text-rose-900";
  return "border-slate-200 bg-white text-slate-700";
}

/**
 * 获取地点类型的中文标签
 */
export function getLocationTypeLabel(locationType: string): string {
  const labels: Record<string, string> = {
    cafe: "咖啡馆",
    plaza: "广场",
    park: "公园",
    shop: "商店",
    home: "住宅",
    office: "办公室",
    hospital: "医院",
  };
  return labels[locationType] ?? locationType;
}

/**
 * 昼夜时段配置
 */
export type TimeOfDay = "dawn" | "morning" | "noon" | "afternoon" | "evening" | "night";

export function getTimeOfDay(hour: number): TimeOfDay {
  if (hour >= 5 && hour < 7) return "dawn";
  if (hour >= 7 && hour < 12) return "morning";
  if (hour >= 12 && hour < 14) return "noon";
  if (hour >= 14 && hour < 18) return "afternoon";
  if (hour >= 18 && hour < 21) return "evening";
  return "night";
}

/**
 * 获取昼夜时段的视觉配置
 */
export function getTimeOfDayStyle(timeOfDay: TimeOfDay): {
  label: string;
  bgGradient: string;
  overlayColor: string;
  icon: string;
  isDark: boolean;
} {
  const styles: Record<TimeOfDay, {
    label: string;
    bgGradient: string;
    overlayColor: string;
    icon: string;
    isDark: boolean;
  }> = {
    dawn: {
      label: "黎明",
      bgGradient: "from-orange-100/30 via-rose-50/20 to-sky-50/30",
      overlayColor: "rgba(251, 191, 36, 0.08)",
      icon: "🌅",
      isDark: false,
    },
    morning: {
      label: "早晨",
      bgGradient: "from-amber-50/40 via-yellow-50/20 to-white",
      overlayColor: "rgba(251, 191, 36, 0.05)",
      icon: "🌄",
      isDark: false,
    },
    noon: {
      label: "正午",
      bgGradient: "from-sky-50/30 via-white to-white",
      overlayColor: "rgba(255, 255, 255, 0.1)",
      icon: "☀️",
      isDark: false,
    },
    afternoon: {
      label: "下午",
      bgGradient: "from-orange-50/20 via-amber-50/20 to-white",
      overlayColor: "rgba(251, 146, 60, 0.05)",
      icon: "🌤️",
      isDark: false,
    },
    evening: {
      label: "傍晚",
      bgGradient: "from-orange-100/40 via-rose-100/30 to-purple-100/20",
      overlayColor: "rgba(249, 115, 22, 0.1)",
      icon: "🌇",
      isDark: false,
    },
    night: {
      label: "夜晚",
      bgGradient: "from-slate-800/60 via-slate-700/40 to-slate-900/50",
      overlayColor: "rgba(15, 23, 42, 0.35)",
      icon: "🌙",
      isDark: true,
    },
  };
  return styles[timeOfDay];
}

export function eventMatchesFilter(event: WorldEvent, filter: EventFilter) {
  if (filter === "all") return true;
  if (filter === "social") {
    return isSocialEvent(event);
  }
  if (filter === "movement") return event.event_type === EVENT_MOVE;
  return event.event_type === EVENT_WORK || event.event_type === EVENT_REST;
}

export function locationBeat(
  locationId: string,
  events: WorldSnapshot["recent_events"],
  locations?: WorldSnapshot["locations"],
  currentTick?: number,
): LocationBeat {
  // 如果地点当前没有人，直接返回 quiet，不依赖历史事件
  if (locations) {
    const loc = locations.find((l) => l.id === locationId);
    if (loc && loc.occupants.length === 0) return "quiet";
  }
  // 只看最新 tick 的事件（当前 tick 或上一 tick），避免历史事件污染当前状态
  const latest = events.find((event) => event.location_id === locationId);
  if (!latest) return "quiet";
  if (currentTick !== undefined && latest.tick_no < currentTick - 1) return "quiet";
  if (
    latest.event_type === EVENT_TALK ||
    latest.event_type === EVENT_SPEECH ||
    latest.event_type === EVENT_LISTEN ||
    latest.event_type === EVENT_CONVERSATION_STARTED ||
    latest.event_type === EVENT_CONVERSATION_JOINED
  ) {
    return "conversation";
  }
  if (latest.event_type === EVENT_MOVE) return "arrival";
  if (latest.event_type === EVENT_WORK) return "working";
  if (latest.event_type === EVENT_REST) return "resting";
  return "quiet";
}

export function beatBadge(beat: LocationBeat | string) {
  const map: Record<LocationBeat, { cls: string; label: string }> = {
    conversation: { cls: "bg-rose-100 text-rose-900", label: "对话中" },
    arrival: { cls: "bg-emerald-100 text-emerald-900", label: "有人抵达" },
    working: { cls: "bg-amber-100 text-amber-900", label: "工作中" },
    resting: { cls: "bg-slate-100 text-slate-800", label: "休息中" },
    quiet: { cls: "bg-white/80 text-slate-500", label: "安静" },
  };

  return map[beat as LocationBeat] ?? { cls: "bg-slate-100 text-slate-700", label: beat };
}

export function formatGoal(goal?: string) {
  if (!goal) {
    return "暂无公开目标";
  }

  return goal.length > 28 ? `${goal.slice(0, 28)}...` : goal;
}

export function formatSimTime(world: WorldSnapshot) {
  if (world.world_clock?.time) {
    return world.world_clock.time;
  }
  return "时间加载中";
}

const WEEKDAY_NAMES_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];

/**
 * 根据 tick 计算模拟世界天数（从第1天开始）和星期（第1天=周一）。
 * 返回如 "第1天 周一" 的字符串。
 *
 * @deprecated 此函数从 tick 累积推算天数，无法反映世界真实起始日期。
 * 有 world_clock 时请直接读取 world_clock.day / world_clock.weekday_name_cn；
 * Timeline 场景请改用 simDayLabelFromIso。
 */
export function simDayLabel(tick: number, tickMinutes: number): string {
  const totalMinutes = tick * tickMinutes;
  const dayIndex = Math.floor(totalMinutes / 1440); // 1440 = 24 * 60
  const dayNumber = dayIndex + 1; // 从第1天开始
  const weekday = WEEKDAY_NAMES_CN[dayIndex % 7];
  return `第${dayNumber}天 ${weekday}`;
}

/**
 * 根据世界起始 ISO 时间和当前世界 ISO 时间，推算天数和星期。
 * 返回如 "第3天 周三" 的字符串。
 * 适用于 Timeline 场景（使用 TimelineRunInfo.world_start_iso + current_world_time_iso）。
 */
export function simDayLabelFromIso(worldStartIso: string, currentWorldTimeIso: string): string {
  const startDate = new Date(worldStartIso);
  const currentDate = new Date(currentWorldTimeIso);
  // 只比较日期部分（去掉时间），避免时区误差影响天数
  const startDay = Date.UTC(startDate.getUTCFullYear(), startDate.getUTCMonth(), startDate.getUTCDate());
  const currentDay = Date.UTC(currentDate.getUTCFullYear(), currentDate.getUTCMonth(), currentDate.getUTCDate());
  const dayIndex = Math.floor((currentDay - startDay) / (1000 * 60 * 60 * 24));
  const dayNumber = Math.max(1, dayIndex + 1);
  const weekday = WEEKDAY_NAMES_CN[dayIndex % 7];
  return `第${dayNumber}天 ${weekday}`;
}

/**
 * 根据当前世界 ISO 时间推算指定 tick 的日历日期与时间。
 * 当缺少 clockIso 时，仅返回 Tick 编号，避免伪造线性时间。
 */
export function tickToSimDayTime(
  tickNo: number,
  tickMinutes: number,
  currentTick: number,
  clockIso?: string,
): string {
  if (clockIso) {
    const offsetMinutes = (tickNo - currentTick) * tickMinutes;
    const targetDate = new Date(new Date(clockIso).getTime() + offsetMinutes * 60 * 1000);
    const month = (targetDate.getUTCMonth() + 1).toString().padStart(2, "0");
    const day = targetDate.getUTCDate().toString().padStart(2, "0");
    const weekday = WEEKDAY_NAMES_CN[(targetDate.getUTCDay() + 6) % 7];
    const hh = targetDate.getUTCHours().toString().padStart(2, "0");
    const mm = targetDate.getUTCMinutes().toString().padStart(2, "0");
    return `${month}-${day} ${weekday} ${hh}:${mm}`;
  }
  return `Tick ${tickNo}`;
}

/**
 * Convert a tick number to a human-readable simulation time string (HH:MM).
 *
 * Strategy:
 * - `clockIso` is the world sim-time ISO string for `currentTick`
 *   (e.g. "2026-03-02T09:30:00+00:00"). We extract HH:MM directly from the
 *   ISO string (characters 11-15) to avoid timezone conversion, then compute
 *   the offset in minutes: (tickNo - currentTick) * tickMinutes.
 * - Falls back to treating tick 0 as 00:00 when no clock is available.
 */
export function tickToSimTime(
  tickNo: number,
  tickMinutes: number,
  currentTick: number,
  clockIso?: string,
): string {
  if (clockIso) {
    const offsetMinutes = (tickNo - currentTick) * tickMinutes;
    const targetDate = new Date(new Date(clockIso).getTime() + offsetMinutes * 60 * 1000);
    const hh = targetDate.getUTCHours().toString().padStart(2, "0");
    const mm = targetDate.getUTCMinutes().toString().padStart(2, "0");
    return `${hh}:${mm}`;
  }
  return `Tick ${tickNo}`;
}

/**
 * 热度配置参数
 */
export interface LocationHeatConfig {
  normalizationBaseline?: number;
  thresholdVeryActive?: number;
  thresholdActive?: number;
  thresholdMild?: number;
  glowThreshold?: number;
}

/**
 * 计算地点的活动热度 (0-1)
 * 基于近期事件数量、重要性和事件类型权重
 */
export function calculateLocationHeat(
  locationId: string,
  events: WorldSnapshot["recent_events"],
  config?: LocationHeatConfig,
): number {
  // 事件类型权重
  const eventWeights: Record<string, number> = {
    [EVENT_SPEECH]: 1.5,
    [EVENT_LISTEN]: 0.9,
    [EVENT_CONVERSATION_STARTED]: 1.1,
    [EVENT_CONVERSATION_JOINED]: 0.8,
    [EVENT_TALK]: 1.5,
    [EVENT_WORK]: 1.0,
    [EVENT_MOVE]: 0.6,
    [EVENT_REST]: 0.4,
    [DIRECTOR_EVENT_INJECT]: 2.0,
    [DIRECTOR_EVENT_BROADCAST]: 2.0,
    [DIRECTOR_EVENT_ACTIVITY]: 2.0,
    [DIRECTOR_EVENT_SHUTDOWN]: 2.0,
    [DIRECTOR_EVENT_WEATHER_CHANGE]: 2.0,
    [EVENT_PLAN]: 0.5,
    [EVENT_REFLECT]: 0.5,
  };

  const locationEvents = events.filter((event) => event.location_id === locationId);

  if (locationEvents.length === 0) return 0;

  // 计算加权热度
  let heat = 0;
  for (const event of locationEvents) {
    const baseWeight = eventWeights[event.event_type] ?? 0.5;
    const importance = (event.payload.importance as number | undefined) ?? 5;
    // 重要度归一化到 0.5-2.0 倍数
    const importanceMultiplier = 0.5 + (importance / 10) * 1.5;
    heat += baseWeight * importanceMultiplier;
  }

  // 归一化：用配置基准（默认 30），约 15-20 条加权事件达到满热度
  const baseline = config?.normalizationBaseline ?? 30;
  const normalizedHeat = Math.min(heat / baseline, 1);

  return normalizedHeat;
}

/**
 * 热度等级配置
 */
export function getHeatLevel(heat: number, config?: LocationHeatConfig): {
  level: string;
  color: string;
  glowColor: string;
  label: string;
} {
  const thVeryActive = config?.thresholdVeryActive ?? 0.7;
  const thActive = config?.thresholdActive ?? 0.4;
  const thMild = config?.thresholdMild ?? 0.15;

  if (heat >= thVeryActive) {
    return {
      level: "hot",
      color: "#ef4444",
      glowColor: "rgba(239, 68, 68, 0.4)",
      label: "非常活跃",
    };
  }
  if (heat >= thActive) {
    return {
      level: "warm",
      color: "#f59e0b",
      glowColor: "rgba(245, 158, 11, 0.35)",
      label: "较活跃",
    };
  }
  if (heat >= thMild) {
    return {
      level: "mild",
      color: "#22c55e",
      glowColor: "rgba(34, 197, 94, 0.25)",
      label: "一般",
    };
  }
  return {
    level: "cool",
    color: "#94a3b8",
    glowColor: "rgba(148, 163, 184, 0.15)",
    label: "安静",
  };
}
