"use client";

import { motion } from "framer-motion";
import { useState, useEffect, type ReactElement } from "react";
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

// 打字机效果组件
function TypewriterText({ text, speed = 30 }: { text: string; speed?: number }): ReactElement {
  const [displayText, setDisplayText] = useState<string>("");
  const [isComplete, setIsComplete] = useState<boolean>(false);

  useEffect(() => {
    setDisplayText("");
    setIsComplete(false);
    let currentIndex = 0;
    
    const timer = setInterval(() => {
      if (currentIndex < text.length) {
        setDisplayText(text.slice(0, currentIndex + 1));
        currentIndex++;
      } else {
        setIsComplete(true);
        clearInterval(timer);
      }
    }, speed);

    return () => clearInterval(timer);
  }, [text, speed]);

  return (
    <span>
      {displayText}
      {!isComplete && (
        <motion.span
          className="inline-block h-4 w-0.5 bg-current align-middle"
          animate={{ opacity: [1, 0] }}
          transition={{ duration: 0.5, repeat: Infinity }}
        />
      )}
    </span>
  );
}

export function EventCard({ 
  event, 
  index, 
  isLatest, 
  agentNameMap, 
  locationNameMap 
}: EventCardProps) {
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
      initial={{ opacity: 0, x: -20, scale: 0.95 }}
      animate={{ opacity: 1, x: 0, scale: 1 }}
      exit={{ opacity: 0, x: 20, scale: 0.95 }}
      transition={{ 
        delay: index * 0.05,
        type: "spring",
        stiffness: 300,
        damping: 24,
      }}
      className={`
        relative overflow-hidden rounded-2xl border-2 px-4 py-3 text-sm
        transition-shadow hover:shadow-md
        ${config.bgColor}
        ${config.borderColor}
        ${isLatest ? "ring-2 ring-offset-2" : ""}
      `}
      style={{
        boxShadow: isLatest ? `0 0 20px ${config.color}40` : undefined,
      }}
    >
      {/* 最新事件脉冲效果 */}
      {isLatest && (
        <motion.div
          className="absolute inset-0 rounded-2xl"
          style={{ backgroundColor: config.color }}
          initial={{ opacity: 0.3 }}
          animate={{ opacity: [0.2, 0, 0.2] }}
          transition={{ duration: 2, repeat: Infinity }}
        />
      )}

      <div className="relative">
        {/* 头部：图标 + 类型 + Tick */}
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2">
            <motion.span 
              className="flex h-8 w-8 items-center justify-center rounded-full bg-white text-lg shadow-sm"
              whileHover={{ scale: 1.1, rotate: 5 }}
              transition={{ type: "spring", stiffness: 400 }}
            >
              {config.icon}
            </motion.span>
            <div>
              <p className="font-medium text-gray-900">
                {isLatest ? (
                  <TypewriterText text={description} speed={20} />
                ) : (
                  <>{description}</>
                )}
              </p>
              {hasMessage && (
                <motion.div 
                  className="mt-1 text-xs italic text-gray-600"
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  transition={{ delay: 0.3 }}
                >
                  「{messageText}」
                </motion.div>
              )}
              {showTalkHint && (
                <motion.div 
                  className="mt-1 text-xs text-gray-400"
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  transition={{ delay: 0.3 }}
                >
                  💭 正在交谈中...
                </motion.div>
              )}
            </div>
          </div>
          <div className="flex flex-col items-end gap-1">
            <span 
              className="rounded-full px-2 py-0.5 text-xs font-medium"
              style={{ 
                backgroundColor: `${config.color}20`,
                color: config.color,
              }}
            >
              {config.label}
            </span>
            <span className="text-xs text-gray-400">
              Tick {event.tick_no}
            </span>
          </div>
        </div>

        {/* 参与者标签 */}
        <div className="mt-2 flex flex-wrap gap-1.5">
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
            <motion.span
              className="rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-700"
              animate={{ scale: [1, 1.05, 1] }}
              transition={{ duration: 1.5, repeat: Infinity }}
            >
              ⭐ 重要 {event.payload.importance as number}
            </motion.span>
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
    <motion.span
      className={`rounded-full px-2 py-0.5 text-xs ${colors[type]}`}
      whileHover={{ scale: 1.05 }}
      transition={{ type: "spring", stiffness: 400 }}
    >
      {label}
    </motion.span>
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
