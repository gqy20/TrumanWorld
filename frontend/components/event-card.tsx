"use client";

import { motion } from "framer-motion";
import {
  EVENT_CONVERSATION_JOINED,
  EVENT_CONVERSATION_STARTED,
  EVENT_SPEECH,
  EVENT_TALK,
} from "@/lib/simulation-protocol";
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
  const isConversationStructure =
    event.event_type === EVENT_CONVERSATION_STARTED ||
    event.event_type === EVENT_CONVERSATION_JOINED;

  const description = describeWorldEvent(event, agentNameMap, locationNameMap);
  const messageText = event.payload.message;
  const hasMessage = typeof messageText === "string" && messageText.length > 0;
  const showTalkHint =
    (event.event_type === EVENT_TALK || event.event_type === EVENT_SPEECH) && !hasMessage;

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
        relative rounded-2xl border px-4 py-3 text-sm
        transition-shadow hover:shadow-xs
        ${
          isConversationStructure
            ? "border-slate-100 bg-slate-50/70"
            : "border-slate-200 bg-white"
        }
        ${isLatest ? "ring-1 ring-offset-1" : ""}
      `}
      style={{
        boxShadow:
          isLatest && !isConversationStructure ? `0 4px 14px ${config.color}18` : undefined,
      }}
    >
      <div
        className="absolute inset-y-3 left-0 w-1 rounded-r-full"
        style={{ backgroundColor: isConversationStructure ? `${config.color}88` : config.color }}
      />
      <div className="relative pl-1">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-start gap-2">
            <span
              className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-sm ${
                isConversationStructure ? "bg-white text-slate-500" : "bg-slate-50 shadow-xs"
              }`}
            >
              {config.icon}
            </span>
            <div className="min-w-0">
              <p className={isConversationStructure ? "text-slate-600" : "font-medium text-gray-900"}>
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
              className={`rounded-full px-2 py-0.5 text-[10px] ${
                isConversationStructure ? "font-normal" : "font-medium"
              }`}
              style={{
                backgroundColor: isConversationStructure ? "rgba(241, 245, 249, 0.95)" : `${config.color}20`,
                color: isConversationStructure ? "#64748b" : config.color,
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
