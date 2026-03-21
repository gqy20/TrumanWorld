"use client";

import { useMemo, useState } from "react";

import {
  formatAgentScore,
  formatMemoryCategory,
  memoryCategoryBadgeClass,
} from "@/lib/agent-utils";
import { describeAgentEvent } from "@/lib/event-utils";
import { tickToSimDayTime } from "@/lib/world-utils";
import type { AgentDetailFilter, AgentDetails, AgentMemory, AgentRecentEvent, WorldSnapshot } from "@/lib/types";

// 事件类型分类
const TALK_TYPES = new Set(["talk", "speech", "conversation_started", "conversation_joined", "listen"]);
const ACTION_TYPES = new Set(["move", "action"]);
const SYSTEM_TYPES = new Set(["rejected", "error"]);

type AgentSignalsPanelProps = {
  agent: AgentDetails;
  world?: WorldSnapshot | null;
  initialFilter?: AgentDetailFilter;
  compact?: boolean;
};

type LocalFilterState = {
  eventType: string;
  eventQuery: string;
  hideRoutineEvents: boolean;
  memoryCategory: string;
  memoryQuery: string;
  minMemoryImportance: string;
};

const ROUTINE_EVENT_TYPES = new Set(["work", "rest"]);

function applyEventFilters(events: AgentRecentEvent[], filter: LocalFilterState) {
  const query = filter.eventQuery.trim().toLowerCase();
  return events.filter((event) => {
    if (filter.eventType && event.event_type !== filter.eventType) return false;
    if (filter.hideRoutineEvents && ROUTINE_EVENT_TYPES.has(event.event_type)) return false;
    if (!query) return true;
    const haystacks = [
      event.event_type,
      event.actor_name,
      event.target_name,
      event.location_name,
      typeof event.payload.message === "string" ? event.payload.message : undefined,
      describeAgentEvent(event),
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return haystacks.includes(query);
  });
}

function applyMemoryFilters(memories: AgentMemory[], filter: LocalFilterState) {
  const query = filter.memoryQuery.trim().toLowerCase();
  const minImportance = filter.minMemoryImportance ? Number(filter.minMemoryImportance) : null;
  return memories.filter((memory) => {
    if (filter.memoryCategory && memory.memory_category !== filter.memoryCategory) return false;
    if (minImportance != null && (memory.importance ?? 0) < minImportance) return false;
    if (!query) return true;
    const haystacks = [
      memory.summary,
      memory.content,
      memory.related_agent_name,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return haystacks.includes(query);
  });
}

export function AgentSignalsPanel({
  agent,
  world,
  initialFilter,
  compact = false,
}: AgentSignalsPanelProps) {
  const [filter, setFilter] = useState<LocalFilterState>({
    eventType: initialFilter?.event_type ?? "",
    eventQuery: initialFilter?.event_query ?? "",
    hideRoutineEvents: initialFilter?.include_routine_events === false,
    memoryCategory: initialFilter?.memory_category ?? "",
    memoryQuery: initialFilter?.memory_query ?? "",
    minMemoryImportance:
      initialFilter?.min_memory_importance != null
        ? String(initialFilter.min_memory_importance)
        : "",
  });

  // 筛选器折叠状态（弹窗内默认收起）
  const [eventFilterOpen, setEventFilterOpen] = useState(false);
  const [memFilterOpen, setMemFilterOpen] = useState(false);

  const eventTypeOptions = useMemo(
    () => Array.from(new Set(agent.recent_events.map((event) => event.event_type))),
    [agent.recent_events],
  );
  const filteredEvents = useMemo(
    () => applyEventFilters(agent.recent_events, filter),
    [agent.recent_events, filter],
  );
  const filteredMemories = useMemo(
    () => applyMemoryFilters(agent.memories, filter),
    [agent.memories, filter],
  );

  // 判断筛选器是否有非默认值（用于显示"已筛选"状态点）
  const hasEventFilter = !!(filter.eventType || filter.eventQuery || filter.hideRoutineEvents);
  const hasMemFilter = !!(filter.memoryCategory || filter.memoryQuery || filter.minMemoryImportance);

  return (
    <div className={`grid gap-4 ${compact ? "h-full grid-cols-2" : "xl:grid-cols-2"}`}>
      {/* ── 行为流 ── */}
      <section className="flex min-h-0 flex-col rounded-2xl border border-slate-200 bg-white shadow-xs">
        {/* 区域标题 */}
        <div className="flex items-center gap-2 border-b border-slate-100 px-4 py-3">
          <span className="h-3.5 w-0.5 rounded-full bg-sky-400" />
          <span className="text-sm font-semibold text-slate-700">行为流</span>
          <span className="ml-1 text-[11px] text-slate-400">
            {filteredEvents.length !== agent.recent_events.length
              ? `${filteredEvents.length} / ${agent.recent_events.length}`
              : agent.recent_events.length}
          </span>
          {/* 筛选器展开按钮 */}
          <button
            type="button"
            onClick={() => setEventFilterOpen((v) => !v)}
            className="ml-auto flex items-center gap-1 rounded-lg px-2 py-1 text-[11px] text-slate-400 transition hover:bg-slate-100 hover:text-slate-600"
          >
            {hasEventFilter && <span className="h-1.5 w-1.5 rounded-full bg-sky-400" />}
            筛选 {eventFilterOpen ? "▴" : "▾"}
          </button>
        </div>

        {/* 筛选器（折叠） */}
        {eventFilterOpen && (
          <div className="grid gap-2 border-b border-slate-100 bg-slate-50/60 px-4 py-3 md:grid-cols-3">
            <div>
              <label htmlFor="agent-event-type" className="mb-1 block text-[10px] font-medium text-slate-400">
                事件类型
              </label>
              <select
                id="agent-event-type"
                value={filter.eventType}
                onChange={(e) => setFilter((c) => ({ ...c, eventType: e.target.value }))}
                className="w-full rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-xs text-slate-700"
              >
                <option value="">全部</option>
                {eventTypeOptions.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <div>
              <label htmlFor="agent-event-query" className="mb-1 block text-[10px] font-medium text-slate-400">
                搜索
              </label>
              <input
                id="agent-event-query"
                value={filter.eventQuery}
                onChange={(e) => setFilter((c) => ({ ...c, eventQuery: e.target.value }))}
                placeholder="消息、地点、对象"
                className="w-full rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-xs text-slate-700"
              />
            </div>
            <label
              htmlFor="agent-hide-routine"
              className="flex items-center gap-2 self-end rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-xs text-slate-600"
            >
              <input
                id="agent-hide-routine"
                type="checkbox"
                checked={filter.hideRoutineEvents}
                onChange={(e) => setFilter((c) => ({ ...c, hideRoutineEvents: e.target.checked }))}
              />
              隐藏例行事件
            </label>
          </div>
        )}

        {/* 事件列表 */}
        <div className="min-h-[160px] flex-1 overflow-y-auto px-3 py-2">
          {filteredEvents.length === 0 ? (
            <p className="py-6 text-center text-sm text-slate-400">暂无匹配事件</p>
          ) : (
            <div className="space-y-1">
              {filteredEvents.map((event) => {
                const isRoutine = ROUTINE_EVENT_TYPES.has(event.event_type);
                const isTalk = TALK_TYPES.has(event.event_type);
                const isAction = ACTION_TYPES.has(event.event_type);
                const isSystem = SYSTEM_TYPES.has(event.event_type);
                const timeLabel = world
                  ? tickToSimDayTime(
                      event.tick_no,
                      world.run.tick_minutes ?? 5,
                      world.run.current_tick ?? 0,
                      world.world_clock?.iso,
                    )
                  : null;

                // 例行事件：极简展示
                if (isRoutine) {
                  return (
                    <div key={event.id} className="flex items-center gap-2 py-0.5 text-[11px] text-slate-400">
                      <span className="flex-1 truncate">{describeAgentEvent(event)}</span>
                      {timeLabel && <span className="shrink-0">{timeLabel}</span>}
                    </div>
                  );
                }

                // 非例行：带颜色的卡片
                const cardStyle = isTalk
                  ? "border-sky-100 bg-sky-50/60"
                  : isSystem
                    ? "border-red-100 bg-red-50/50"
                    : isAction
                      ? "border-amber-100 bg-amber-50/50"
                      : "border-slate-100 bg-white";

                const typeTagStyle = isTalk
                  ? "text-sky-500"
                  : isSystem
                    ? "text-red-500"
                    : isAction
                      ? "text-amber-600"
                      : "text-slate-400";

                return (
                  <article key={event.id} className={`rounded-xl border px-3 py-2 ${cardStyle}`}>
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className={`text-[10px] uppercase tracking-wider ${typeTagStyle}`}>{event.event_type}</p>
                        <p className="mt-0.5 text-xs leading-snug text-slate-700">{describeAgentEvent(event)}</p>
                      </div>
                      <span className="shrink-0 text-[10px] text-slate-400">
                        {timeLabel ?? `T${event.tick_no}`}
                      </span>
                    </div>
                    {(event.target_name || event.location_name) && (
                      <div className="mt-1.5 flex flex-wrap gap-1">
                        {event.target_name && (
                          <span className="rounded-full border border-rose-100 bg-rose-50 px-1.5 py-0.5 text-[10px] text-rose-600">
                            → {event.target_name}
                          </span>
                        )}
                        {event.location_name && (
                          <span className="rounded-full border border-slate-100 bg-slate-50 px-1.5 py-0.5 text-[10px] text-slate-500">
                            📍 {event.location_name}
                          </span>
                        )}
                      </div>
                    )}
                  </article>
                );
              })}
            </div>
          )}
        </div>
      </section>

      {/* ── 记忆栈 ── */}
      <section className="flex min-h-0 flex-col rounded-2xl border border-slate-200 bg-white shadow-xs">
        {/* 区域标题 */}
        <div className="flex items-center gap-2 border-b border-slate-100 px-4 py-3">
          <span className="h-3.5 w-0.5 rounded-full bg-amber-400" />
          <span className="text-sm font-semibold text-slate-700">记忆栈</span>
          <span className="ml-1 text-[11px] text-slate-400">
            {filteredMemories.length !== agent.memories.length
              ? `${filteredMemories.length} / ${agent.memories.length}`
              : agent.memories.length}
          </span>
          <button
            type="button"
            onClick={() => setMemFilterOpen((v) => !v)}
            className="ml-auto flex items-center gap-1 rounded-lg px-2 py-1 text-[11px] text-slate-400 transition hover:bg-slate-100 hover:text-slate-600"
          >
            {hasMemFilter && <span className="h-1.5 w-1.5 rounded-full bg-amber-400" />}
            筛选 {memFilterOpen ? "▴" : "▾"}
          </button>
        </div>

        {/* 记忆筛选器（折叠） */}
        {memFilterOpen && (
          <div className="grid gap-2 border-b border-slate-100 bg-slate-50/60 px-4 py-3 md:grid-cols-3">
            <div>
              <label htmlFor="agent-memory-category" className="mb-1 block text-[10px] font-medium text-slate-400">
                层级
              </label>
              <select
                id="agent-memory-category"
                value={filter.memoryCategory}
                onChange={(e) => setFilter((c) => ({ ...c, memoryCategory: e.target.value }))}
                className="w-full rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-xs text-slate-700"
              >
                <option value="">全部</option>
                <option value="short_term">短期</option>
                <option value="medium_term">中期</option>
                <option value="long_term">长期</option>
              </select>
            </div>
            <div>
              <label htmlFor="agent-memory-query" className="mb-1 block text-[10px] font-medium text-slate-400">
                搜索
              </label>
              <input
                id="agent-memory-query"
                value={filter.memoryQuery}
                onChange={(e) => setFilter((c) => ({ ...c, memoryQuery: e.target.value }))}
                placeholder="摘要、内容、关联对象"
                className="w-full rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-xs text-slate-700"
              />
            </div>
            <div>
              <label htmlFor="agent-memory-importance" className="mb-1 block text-[10px] font-medium text-slate-400">
                最低重要性
              </label>
              <select
                id="agent-memory-importance"
                value={filter.minMemoryImportance}
                onChange={(e) => setFilter((c) => ({ ...c, minMemoryImportance: e.target.value }))}
                className="w-full rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-xs text-slate-700"
              >
                <option value="">全部</option>
                <option value="0.3">0.3+</option>
                <option value="0.5">0.5+</option>
                <option value="0.8">0.8+</option>
                <option value="0.95">0.95+</option>
              </select>
            </div>
          </div>
        )}

        {/* 记忆列表 */}
        <div className="min-h-[160px] flex-1 overflow-y-auto px-3 py-2">
          {filteredMemories.length === 0 ? (
            <p className="py-6 text-center text-sm text-slate-400">暂无匹配记忆</p>
          ) : (
            <div className="space-y-1.5">
              {filteredMemories.map((memory) => {
                const imp = memory.importance ?? 0;
                const isHighImp = imp >= 0.7;
                const isLowImp = imp < 0.3;
                const impPct = `${(imp * 100).toFixed(0)}%`;

                // 低重要度记忆：降噪展示
                if (isLowImp) {
                  return (
                    <div key={memory.id} className="flex items-center gap-2 py-0.5 text-[11px] text-slate-400">
                      <span className="flex-1 line-clamp-1">{memory.content}</span>
                      <span className={`shrink-0 rounded-full border px-1.5 py-0.5 text-[10px] ${memoryCategoryBadgeClass(memory.memory_category)}`}>
                        {formatMemoryCategory(memory.memory_category)}
                      </span>
                    </div>
                  );
                }

                const cardStyle = isHighImp
                  ? "border-amber-100 bg-amber-50/40"
                  : "border-slate-100 bg-white";

                return (
                  <article key={memory.id} className={`rounded-xl border px-3 py-2.5 ${cardStyle}`}>
                    <div className="mb-1.5 flex items-center gap-1.5">
                      <span className={`rounded-full border px-1.5 py-0.5 text-[10px] ${memoryCategoryBadgeClass(memory.memory_category)}`}>
                        {formatMemoryCategory(memory.memory_category)}
                      </span>
                      {memory.related_agent_name && (
                        <span className="rounded-full border border-rose-100 bg-rose-50 px-1.5 py-0.5 text-[10px] text-rose-600">
                          {memory.related_agent_name}
                        </span>
                      )}
                      {/* 重要度进度条 */}
                      <div className="ml-auto flex items-center gap-1.5">
                        <div className="h-[4px] w-12 overflow-hidden rounded-full bg-slate-100">
                          <div
                            className={`h-full rounded-full ${isHighImp ? "bg-amber-400" : "bg-slate-300"}`}
                            style={{ width: impPct }}
                          />
                        </div>
                        <span className={`text-[10px] tabular-nums ${isHighImp ? "text-amber-600" : "text-slate-400"}`}>
                          {formatAgentScore(memory.importance)}
                        </span>
                      </div>
                    </div>
                    <p className="text-xs leading-relaxed text-slate-700">{memory.content}</p>
                  </article>
                );
              })}
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

