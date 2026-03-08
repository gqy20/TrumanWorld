import {
  DIRECTOR_EVENT_ACTIVITY,
  DIRECTOR_EVENT_BROADCAST,
  DIRECTOR_EVENT_INJECT,
  DIRECTOR_EVENT_SHUTDOWN,
  DIRECTOR_EVENT_WEATHER_CHANGE,
  EVENT_MOVE,
  EVENT_PLAN,
  EVENT_REFLECT,
  EVENT_REST,
  EVENT_TALK,
  EVENT_WORK,
} from "@/lib/simulation-protocol";
import type { WorldEvent, WorldSnapshot } from "@/lib/types";
export type LocationBeat = "conversation" | "arrival" | "working" | "resting" | "quiet";
export type EventFilter = "all" | "social" | "activity" | "movement";

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
  if (filter === "social") return event.event_type === EVENT_TALK;
  if (filter === "movement") return event.event_type === EVENT_MOVE;
  return event.event_type === EVENT_WORK || event.event_type === EVENT_REST;
}

export function locationBeat(locationId: string, events: WorldSnapshot["recent_events"]): LocationBeat {
  const latest = events.find((event) => event.location_id === locationId);
  if (!latest) return "quiet";
  if (latest.event_type === EVENT_TALK) return "conversation";
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
  const tickMinutes = world.run.tick_minutes ?? 5;
  const totalMinutes = (world.run.current_tick ?? 0) * tickMinutes;
  const hours = Math.floor(totalMinutes / 60)
    .toString()
    .padStart(2, "0");
  const minutes = (totalMinutes % 60).toString().padStart(2, "0");

  return `${hours}:${minutes}`;
}

const WEEKDAY_NAMES_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];

/**
 * 根据 tick 计算模拟世界天数（从第1天开始）和星期（第1天=周一）。
 * 返回如 "第1天 周一" 的字符串。
 */
export function simDayLabel(tick: number, tickMinutes: number): string {
  const totalMinutes = tick * tickMinutes;
  const dayIndex = Math.floor(totalMinutes / 1440); // 1440 = 24 * 60
  const dayNumber = dayIndex + 1; // 从第1天开始
  const weekday = WEEKDAY_NAMES_CN[dayIndex % 7];
  return `第${dayNumber}天 ${weekday}`;
}

/**
 * 根据 tick 计算模拟时间，返回 "第N天 周X HH:MM" 格式。
 * 时间从模拟开始时刻（由 clockIso 或默认 00:00 决定）推算。
 */
export function tickToSimDayTime(
  tickNo: number,
  tickMinutes: number,
  currentTick: number,
  clockIso?: string,
): string {
  let totalMinutes: number;
  if (clockIso) {
    const timePart = clockIso.substring(11, 16);
    const [hhStr, mmStr] = timePart.split(":");
    const currentTotalMinutes = parseInt(hhStr, 10) * 60 + parseInt(mmStr, 10);
    const offsetMinutes = (tickNo - currentTick) * tickMinutes;
    totalMinutes = ((currentTotalMinutes + offsetMinutes) % (24 * 60) + 24 * 60) % (24 * 60);
    // 计算当前tick对应的绝对分钟数（用于推算天数）
    // 取 clockIso 的日期部分推算绝对分钟
    const dateStr = clockIso.substring(0, 10); // YYYY-MM-DD
    const [, , dayStr] = dateStr.split("-");
    // 简单：直接基于 currentTick 对应的累计分钟数推算天数
    const currentAbsoluteMinutes = currentTick * tickMinutes;
    const absoluteMinutes = currentAbsoluteMinutes + (tickNo - currentTick) * tickMinutes;
    const dayIndex = Math.floor(absoluteMinutes / 1440);
    const dayNumber = dayIndex + 1;
    const weekday = WEEKDAY_NAMES_CN[dayIndex % 7];
    const hh = Math.floor(totalMinutes / 60).toString().padStart(2, "0");
    const mm = (totalMinutes % 60).toString().padStart(2, "0");
    void dayStr;
    return `第${dayNumber}天 ${weekday} ${hh}:${mm}`;
  }
  // Fallback: tick 0 = 第1天 周一 00:00
  const absoluteMinutes = tickNo * tickMinutes;
  const dayIndex = Math.floor(absoluteMinutes / 1440);
  const dayNumber = dayIndex + 1;
  const weekday = WEEKDAY_NAMES_CN[dayIndex % 7];
  totalMinutes = absoluteMinutes % 1440;
  const hh = Math.floor(totalMinutes / 60).toString().padStart(2, "0");
  const mm = (totalMinutes % 60).toString().padStart(2, "0");
  return `第${dayNumber}天 ${weekday} ${hh}:${mm}`;
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
    // Extract HH:MM directly from ISO string (avoids local timezone conversion)
    // ISO format: 2026-03-02T09:30:00+00:00 → index 11..15 = "09:30"
    const timePart = clockIso.substring(11, 16); // "HH:MM"
    const [hhStr, mmStr] = timePart.split(":");
    const currentTotalMinutes = parseInt(hhStr, 10) * 60 + parseInt(mmStr, 10);
    const offsetMinutes = (tickNo - currentTick) * tickMinutes;
    // Keep result within [0, 24*60) wrapping around midnight
    const totalMinutes = ((currentTotalMinutes + offsetMinutes) % (24 * 60) + 24 * 60) % (24 * 60);
    const hh = Math.floor(totalMinutes / 60).toString().padStart(2, "0");
    const mm = (totalMinutes % 60).toString().padStart(2, "0");
    return `${hh}:${mm}`;
  }
  // Fallback: treat tick 0 as 00:00
  const totalMinutes = tickNo * tickMinutes;
  const hh = Math.floor(totalMinutes / 60).toString().padStart(2, "0");
  const mm = (totalMinutes % 60).toString().padStart(2, "0");
  return `${hh}:${mm}`;
}

/**
 * 计算地点的活动热度 (0-1)
 * 基于近期事件数量、重要性和事件类型权重
 */
export function calculateLocationHeat(
  locationId: string,
  events: WorldSnapshot["recent_events"],
): number {
  // 事件类型权重
  const eventWeights: Record<string, number> = {
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

  // 归一化：假设最大热度为 10（约 5-7 个加权事件）
  const normalizedHeat = Math.min(heat / 10, 1);

  return normalizedHeat;
}

/**
 * 热度等级配置
 */
export function getHeatLevel(heat: number): {
  level: string;
  color: string;
  glowColor: string;
  label: string;
} {
  if (heat >= 0.8) {
    return {
      level: "hot",
      color: "#ef4444",
      glowColor: "rgba(239, 68, 68, 0.4)",
      label: "非常活跃",
    };
  }
  if (heat >= 0.5) {
    return {
      level: "warm",
      color: "#f59e0b",
      glowColor: "rgba(245, 158, 11, 0.35)",
      label: "较活跃",
    };
  }
  if (heat >= 0.25) {
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
