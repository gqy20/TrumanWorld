"use client";

import { motion } from "framer-motion";
import type { WorldSnapshot } from "@/lib/api";

type WorldEvent = WorldSnapshot["recent_events"][number];

interface EventCardProps {
  event: WorldEvent;
  index: number;
  isLatest: boolean;
  agentNameMap: Record<string, string>;
  locationNameMap: Record<string, string>;
}

// 事件类型配置
const EVENT_CONFIG: Record<string, { 
  icon: string; 
  label: string; 
  color: string;
  bgColor: string;
  borderColor: string;
}> = {
  talk: { 
    icon: "💬", 
    label: "对话", 
    color: "#ec4899",
    bgColor: "bg-pink-50",
    borderColor: "border-pink-200",
  },
  move: { 
    icon: "🚶", 
    label: "移动", 
    color: "#10b981",
    bgColor: "bg-emerald-50",
    borderColor: "border-emerald-200",
  },
  work: { 
    icon: "⚒️", 
    label: "工作", 
    color: "#f59e0b",
    bgColor: "bg-amber-50",
    borderColor: "border-amber-200",
  },
  rest: { 
    icon: "😴", 
    label: "休息", 
    color: "#6366f1",
    bgColor: "bg-indigo-50",
    borderColor: "border-indigo-200",
  },
  director_inject: { 
    icon: "📢", 
    label: "导演注入", 
    color: "#dc2626",
    bgColor: "bg-red-50",
    borderColor: "border-red-200",
  },
  plan: { 
    icon: "📋", 
    label: "计划", 
    color: "#8b5cf6",
    bgColor: "bg-violet-50",
    borderColor: "border-violet-200",
  },
  reflect: { 
    icon: "🔍", 
    label: "反思", 
    color: "#06b6d4",
    bgColor: "bg-cyan-50",
    borderColor: "border-cyan-200",
  },
};

export function EventCard({
  event,
  index,
  isLatest,
  agentNameMap,
  locationNameMap
}: EventCardProps) {
  // isLatest 用于高亮样式，保留参数以保持接口兼容性
  const config = EVENT_CONFIG[event.event_type] || {
    icon: "✨",
    label: event.event_type,
    color: "#6b7280",
    bgColor: "bg-gray-50",
    borderColor: "border-gray-200",
  };

  const description = describeEvent(event, agentNameMap, locationNameMap);
  const messageText = event.payload.message;
  const hasMessage = typeof messageText === "string" && messageText.length > 0;
  
  // 对于 talk 事件，如果没有具体消息，显示一个默认提示
  const showTalkHint = event.event_type === "talk" && !hasMessage;

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{
        delay: index * 0.03,
        type: "spring",
        stiffness: 400,
        damping: 28,
      }}
      className={`
        relative rounded-xl border px-3 py-2.5 text-sm
        transition-shadow hover:shadow-sm
        ${config.bgColor}
        ${config.borderColor}
        ${isLatest ? "ring-1 ring-offset-1" : ""}
      `}
      style={{
        boxShadow: isLatest ? `0 2px 8px ${config.color}30` : undefined,
      }}
    >
      <div className="relative">
        {/* 头部：图标 + 类型 + Tick */}
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-start gap-2">
            <span className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-white text-sm shadow-sm">
              {config.icon}
            </span>
            <div className="min-w-0">
              <p className="font-medium text-gray-900">
                {description}
              </p>
              {hasMessage && (
                <p className="mt-0.5 text-xs italic text-gray-600">
                  「{messageText}」
                </p>
              )}
              {showTalkHint && (
                <p className="mt-0.5 text-xs text-gray-400">
                  💭 正在交谈中...
                </p>
              )}
            </div>
          </div>
          <div className="flex flex-shrink-0 flex-col items-end gap-0.5">
            <span
              className="rounded-full px-1.5 py-0.5 text-[10px] font-medium"
              style={{
                backgroundColor: `${config.color}20`,
                color: config.color,
              }}
            >
              {config.label}
            </span>
            <span className="text-[10px] text-gray-400">
              T{event.tick_no}
            </span>
          </div>
        </div>

        {/* 参与者标签 */}
        <div className="mt-1.5 flex flex-wrap gap-1">
          {event.actor_agent_id && (
            <EventTag
              label={agentNameMap[event.actor_agent_id] || event.actor_agent_id}
              type="actor"
            />
          )}
          {event.target_agent_id && (
            <EventTag
              label={`→ ${agentNameMap[event.target_agent_id] || event.target_agent_id}`}
              type="target"
            />
          )}
          {event.location_id && (
            <EventTag
              label={`📍 ${locationNameMap[event.location_id] || event.location_id}`}
              type="location"
            />
          )}
          {(event.payload.importance as number | undefined) && (event.payload.importance as number) >= 7 && (
            <span className="rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] text-amber-700">
              ⭐ {event.payload.importance as number}
            </span>
          )}
        </div>
      </div>
    </motion.div>
  );
}

// 事件标签组件
function EventTag({ label, type }: { label: string; type: "actor" | "target" | "location" }) {
  const colors = {
    actor: "bg-sky-100 text-sky-700",
    target: "bg-rose-100 text-rose-700",
    location: "bg-emerald-100 text-emerald-700",
  };

  return (
    <span className={`rounded-full px-1.5 py-0.5 text-[10px] ${colors[type]}`}>
      {label}
    </span>
  );
}

// 描述事件
function describeEvent(
  event: WorldEvent,
  nameMap: Record<string, string>,
  locationMap: Record<string, string>,
): string {
  const actor = nameMap[event.actor_agent_id ?? ""] || event.actor_agent_id || "有人";
  const target = nameMap[event.target_agent_id ?? ""] || event.target_agent_id || "某人";
  const atPlace = locationMap[event.location_id ?? ""] || event.location_id || "小镇";
  const toPlace =
    locationMap[String(event.payload.to_location_id ?? "")] ||
    String(event.payload.to_location_id || atPlace);

  switch (event.event_type) {
    case "move":
      return `${actor} 前往了 ${toPlace}`;
    case "talk":
      return `${actor} 与 ${target} 展开交谈`;
    case "work":
      return `${actor} 在 ${atPlace} 专心工作`;
    case "rest":
      return `${actor} 在 ${atPlace} 休息`;
    case "director_inject":
      return `导演播报：${String(event.payload.message || "发生了一件大事")}`;
    case "plan":
      return `${actor} 制定了新的计划`;
    case "reflect":
      return `${actor} 陷入了沉思`;
    default:
      return `${atPlace} 发生了一些事情`;
  }
}
