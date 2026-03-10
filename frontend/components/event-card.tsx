"use client";

import { motion } from "framer-motion";
import { EVENT_TALK } from "@/lib/simulation-protocol";
import type { WorldEvent } from "@/lib/types";
import { describeWorldEvent, getEventMeta } from "@/lib/event-utils";

interface EventCardProps {
  event: WorldEvent;
  index: number;
  isLatest: boolean;
  agentNameMap: Record<string, string>;
  locationNameMap: Record<string, string>;
  simTime?: string; // formatted HH:MM simulation time for this event's tick
}

export function EventCard({
  event,
  index,
  isLatest,
  agentNameMap,
  locationNameMap,
  simTime,
}: EventCardProps) {
  const config = getEventMeta(event.event_type);

  const description = describeWorldEvent(event, agentNameMap, locationNameMap);
  const messageText = event.payload.message;
  const hasMessage = typeof messageText === "string" && messageText.length > 0;
  const showTalkHint = event.event_type === EVENT_TALK && !hasMessage;

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
        relative rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm
        transition-shadow hover:shadow-xs
        ${isLatest ? "ring-1 ring-offset-1" : ""}
      `}
      style={{
        boxShadow: isLatest ? `0 4px 14px ${config.color}18` : undefined,
      }}
    >
      <div
        className="absolute inset-y-3 left-0 w-1 rounded-r-full"
        style={{ backgroundColor: config.color }}
      />
      <div className="relative pl-1">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-start gap-2">
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-50 text-sm shadow-xs">
              {config.icon}
            </span>
            <div className="min-w-0">
              <p className="font-medium text-gray-900">
                {description}
              </p>
              {hasMessage && (
                <p className="mt-1 text-xs italic leading-5 text-gray-600">
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
          <div className="flex shrink-0 flex-col items-end gap-0.5">
            <span
              className="rounded-full px-2 py-0.5 text-[10px] font-medium"
              style={{
                backgroundColor: `${config.color}20`,
                color: config.color,
              }}
            >
              {config.label}
            </span>
            <span className="text-[10px] text-gray-400">
              T{event.tick_no}{simTime ? ` · ${simTime}` : ""}
            </span>
          </div>
        </div>

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
            <span className="rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] text-amber-700">
              ⭐ {event.payload.importance as number}
            </span>
          )}
        </div>
      </div>
    </motion.div>
  );
}

function EventTag({ label, type }: { label: string; type: "actor" | "target" | "location" }) {
  const colors = {
    actor: "bg-sky-50 text-sky-700 border border-sky-100",
    target: "bg-rose-50 text-rose-700 border border-rose-100",
    location: "bg-emerald-50 text-emerald-700 border border-emerald-100",
  };

  return (
    <span className={`rounded-full px-2 py-0.5 text-[10px] ${colors[type]}`}>
      {label}
    </span>
  );
}
