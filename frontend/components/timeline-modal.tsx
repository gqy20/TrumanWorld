"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Modal } from "@/components/modal";
import { getApiBaseUrl } from "@/lib/api";
import type { AgentSummary, TimelineEvent, TimelineResponse } from "@/lib/types";
import { describeTimelineEvent, getEventMeta } from "@/lib/event-utils";
import { simDayLabelFromIso, tickToSimDayTime } from "@/lib/world-utils";

const EVENT_TYPE_OPTIONS = [
  { value: "", label: "全部类型" },
  { value: "speech,listen,conversation_started,conversation_joined,talk", label: "💬 社交" },
  { value: "move", label: "🚶 移动" },
  { value: "work", label: "⚒️ 工作" },
  { value: "rest", label: "😴 休息" },
  { value: "plan", label: "📋 计划" },
  { value: "reflect", label: "🔍 反思" },
  {
    value:
      "director_inject,director_broadcast,director_activity,director_shutdown,director_weather_change,director_power_outage",
    label: "📢 导演注入",
  },
  { value: "move_rejected,talk_rejected,work_rejected,rest_rejected", label: "❌ 被拒动作" },
];

type Filters = {
  tickFrom: string;
  tickTo: string;
  worldDatetimeFrom: string;
  worldDatetimeTo: string;
  eventType: string;
  agentId: string;
};

const EMPTY_FILTERS: Filters = {
  tickFrom: "",
  tickTo: "",
  worldDatetimeFrom: "",
  worldDatetimeTo: "",
  eventType: "",
  agentId: "",
};

const PAGE_SIZE = 180;
const INITIAL_VISIBLE_GROUPS = 8;
const LOAD_MORE_GROUPS = 8;

interface TimelineModalProps {
  isOpen: boolean;
  onClose: () => void;
  runId: string;
  agents?: AgentSummary[];
}

function buildTimelineUrl(
  baseUrl: string,
  runId: string,
  f: Filters,
  limit: number,
  offset: number,
  orderDesc: boolean = true,
): string {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (f.tickFrom) params.set("tick_from", f.tickFrom);
  if (f.tickTo) params.set("tick_to", f.tickTo);
  if (f.worldDatetimeFrom) params.set("world_datetime_from", f.worldDatetimeFrom);
  if (f.worldDatetimeTo) params.set("world_datetime_to", f.worldDatetimeTo);
  if (f.eventType) params.set("event_type", f.eventType);
  if (f.agentId) params.set("agent_id", f.agentId);
  if (orderDesc) params.set("order_desc", "true");
  return `${baseUrl}/runs/${runId}/timeline?${params.toString()}`;
}

export function TimelineModal({ isOpen, onClose, runId, agents = [] }: TimelineModalProps) {
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [pendingFilters, setPendingFilters] = useState<Filters>(EMPTY_FILTERS);
  const [timeline, setTimeline] = useState<TimelineResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [visibleGroupCount, setVisibleGroupCount] = useState(INITIAL_VISIBLE_GROUPS);
  const timelineRef = useRef<TimelineResponse | null>(null);
  const listContainerRef = useRef<HTMLDivElement | null>(null);
  const loadMoreRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    timelineRef.current = timeline;
  }, [timeline]);

  useEffect(() => {
    if (isOpen) return;
    setTimeline(null);
    setLoading(true);
    setError(null);
    setIsRefreshing(false);
    setIsLoadingMore(false);
    setVisibleGroupCount(INITIAL_VISIBLE_GROUPS);
    timelineRef.current = null;
  }, [isOpen]);

  const fetchTimeline = useCallback(
    async (
      appliedFilters: Filters,
      {
        orderDesc = true,
        append = false,
      }: {
        orderDesc?: boolean;
        append?: boolean;
      } = {},
    ) => {
      const hasExistingData = timelineRef.current !== null;
      const nextOffset = append ? timelineRef.current?.events.length ?? 0 : 0;

      if (append) {
        setIsLoadingMore(true);
      } else if (hasExistingData) {
        setIsRefreshing(true);
      } else {
        setLoading(true);
      }
      setError(null);
      try {
        const url = buildTimelineUrl(
          getApiBaseUrl(),
          runId,
          appliedFilters,
          PAGE_SIZE,
          nextOffset,
          orderDesc,
        );
        const res = await fetch(url, { cache: "no-store", headers: { Accept: "application/json" } });
        if (!res.ok) throw new Error(`请求失败: ${res.status}`);
        const data = (await res.json()) as TimelineResponse;
        if (append && timelineRef.current) {
          const existingEvents = timelineRef.current.events;
          const mergedEvents = [...existingEvents];
          const knownIds = new Set(existingEvents.map((event) => event.id));
          for (const event of data.events) {
            if (!knownIds.has(event.id)) {
              mergedEvents.push(event);
            }
          }
          setTimeline({
            ...data,
            events: mergedEvents,
          });
        } else {
          setTimeline(data);
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "加载失败");
        if (!hasExistingData) {
          setTimeline(null);
        }
      } finally {
        setLoading(false);
        setIsRefreshing(false);
        setIsLoadingMore(false);
      }
    },
    [runId],
  );

  // 打开时加载数据
  useEffect(() => {
    if (isOpen) {
      setVisibleGroupCount(INITIAL_VISIBLE_GROUPS);
      void fetchTimeline(EMPTY_FILTERS);
    }
  }, [isOpen, fetchTimeline]);

  const handleSearch = () => {
    setFilters(pendingFilters);
    setVisibleGroupCount(INITIAL_VISIBLE_GROUPS);
    void fetchTimeline(pendingFilters);
  };

  const handleReset = () => {
    setPendingFilters(EMPTY_FILTERS);
    setFilters(EMPTY_FILTERS);
    setVisibleGroupCount(INITIAL_VISIBLE_GROUPS);
    void fetchTimeline(EMPTY_FILTERS);
  };

  const groups = useMemo(() => {
    if (!timeline) return [];
    const grouped: Record<number, TimelineEvent[]> = {};
    for (const event of timeline.events) {
      (grouped[event.tick_no] ??= []).push(event);
    }
    return Object.entries(grouped).sort(([a], [b]) => Number(b) - Number(a));
  }, [timeline]);

  const importantCount = useMemo(
    () => (timeline?.events ?? []).filter((e) => (e.importance ?? 0) >= 7).length,
    [timeline],
  );

  const total = timeline?.total ?? 0;
  const filtered = timeline?.filtered ?? 0;
  const hasFilter = Object.values(filters).some(Boolean);
  const visibleGroups = useMemo(
    () => groups.slice(0, visibleGroupCount),
    [groups, visibleGroupCount],
  );
  const hasMoreGroups = groups.length > visibleGroupCount;
  const hasMoreEvents = timeline != null && timeline.events.length < (timeline.filtered || timeline.total);

  useEffect(() => {
    const root = listContainerRef.current;
    const target = loadMoreRef.current;
    if (!root || !target) return;
    if (loading || isRefreshing || isLoadingMore) return;
    if (!hasMoreGroups && !hasMoreEvents) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const entry = entries[0];
        if (!entry?.isIntersecting) return;

        if (hasMoreGroups) {
          setVisibleGroupCount((current) => Math.min(current + LOAD_MORE_GROUPS, groups.length));
          return;
        }

        if (hasMoreEvents) {
          void fetchTimeline(filters, { append: true });
        }
      },
      {
        root,
        rootMargin: "0px 0px 240px 0px",
        threshold: 0.1,
      },
    );

    observer.observe(target);
    return () => observer.disconnect();
  }, [
    fetchTimeline,
    filters,
    groups.length,
    hasMoreEvents,
    hasMoreGroups,
    isLoadingMore,
    isRefreshing,
    loading,
  ]);

  const updatePending = (key: keyof Filters, value: string) =>
    setPendingFilters((prev) => ({ ...prev, [key]: value }));

  const inputCls =
    "w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-ink placeholder-slate-300 focus:border-moss focus:outline-hidden";
  const labelCls = "text-[11px] uppercase tracking-[0.15em] text-slate-400";

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      variant="fullscreen"
      showCloseButton={false}
      title="🎬 事件回放"
      subtitle="按 tick 回放事件流，适合复盘剧情节点和角色行为链路"
    >
      <div className="flex min-h-0 flex-1 overflow-hidden">
        {/* 左侧过滤面板 */}
        <aside className="flex w-72 shrink-0 flex-col border-r border-slate-100 bg-slate-50/50">
          <div className="flex-1 overflow-y-auto p-4">
            {/* 摘要卡片 */}
            <section className="rounded-2xl border border-white/70 bg-white/80 p-4 shadow-xs backdrop-blur-sm">
              <p className="text-[11px] uppercase tracking-[0.15em] text-moss">回放摘要</p>
              <div className="mt-3 grid grid-cols-2 gap-2">
                <div className="rounded-xl bg-mist px-3 py-2.5">
                  <p className="text-[10px] text-slate-400">总事件</p>
                  <p className="mt-1 text-base font-semibold text-ink">{total}</p>
                </div>
                <div className="rounded-xl bg-mist px-3 py-2.5">
                  <p className="text-[10px] text-slate-400">当前页</p>
                  <p className="mt-1 text-base font-semibold text-ink">{timeline?.events.length ?? 0}</p>
                </div>
                <div className="rounded-xl bg-mist px-3 py-2.5">
                  <p className="text-[10px] text-slate-400">重要事件</p>
                  <p className="mt-1 text-base font-semibold text-ink">{importantCount}</p>
                </div>
                <div className="rounded-xl bg-mist px-3 py-2.5">
                  <p className="text-[10px] text-slate-400">Tick 组</p>
                  <p className="mt-1 text-base font-semibold text-ink">{groups.length}</p>
                </div>
              </div>
              {hasFilter && (
                <p className="mt-2 text-[10px] text-slate-400">
                  匹配 <span className="font-semibold text-moss">{filtered}</span> / {total} 条
                </p>
              )}
            </section>

            {/* 搜索过滤 */}
            <section className="mt-3 rounded-2xl border border-white/70 bg-white/80 p-4 shadow-xs backdrop-blur-sm">
              <p className="text-[11px] uppercase tracking-[0.15em] text-moss">检索过滤</p>
              <div className="mt-3 space-y-3">
                {/* Tick 范围 - 与世界时间同步 */}
                <div>
                  <label className={labelCls}>Tick 范围</label>
                  <div className="mt-1.5 space-y-2">
                    <div className="grid grid-cols-2 gap-2">
                      <input
                        type="number"
                        placeholder="起始 Tick"
                        className={inputCls}
                        value={pendingFilters.tickFrom}
                        onChange={(e) => updatePending("tickFrom", e.target.value)}
                      />
                      <input
                        type="number"
                        placeholder="结束 Tick"
                        className={inputCls}
                        value={pendingFilters.tickTo}
                        onChange={(e) => updatePending("tickTo", e.target.value)}
                      />
                    </div>
                    {/* 显示对应的模拟时间 */}
                    {timeline?.run_info && (
                      <div className="space-y-1 text-[10px] text-slate-400">
                        {pendingFilters.tickFrom && (
                          <div className="flex items-center gap-1">
                            <span>起始:</span>
                            <span className="text-moss">
                              {tickToSimDayTime(
                                Number(pendingFilters.tickFrom),
                                timeline.run_info.tick_minutes,
                                timeline.run_info.current_tick,
                                timeline.run_info.current_world_time_iso
                              )}
                            </span>
                          </div>
                        )}
                        {pendingFilters.tickTo && (
                          <div className="flex items-center gap-1">
                            <span>结束:</span>
                            <span className="text-moss">
                              {tickToSimDayTime(
                                Number(pendingFilters.tickTo),
                                timeline.run_info.tick_minutes,
                                timeline.run_info.current_tick,
                                timeline.run_info.current_world_time_iso
                              )}
                            </span>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>

                {/* 事件类型 */}
                <div>
                  <label className={labelCls}>事件类型</label>
                  <select
                    className={`${inputCls} appearance-none bg-[url('data:image/svg+xml;charset=UTF-8,%3csvg xmlns=%27http://www.w3.org/2000/svg%27 viewBox=%270 0 24 24%27 fill=%27none%27 stroke=%27currentColor%27 stroke-width=%272%27%3e%3cpath d=%27M6 9l6 6 6-6%27/%3e%3c/svg%3e')] bg-size-[1rem] bg-position-[right_0.5rem_center] bg-no-repeat pr-8`}
                    value={pendingFilters.eventType}
                    onChange={(e) => updatePending("eventType", e.target.value)}
                  >
                    {EVENT_TYPE_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </div>

                {/* 角色 */}
                <div>
                  <label className={labelCls}>角色</label>
                  <select
                    className={`${inputCls} appearance-none bg-[url('data:image/svg+xml;charset=UTF-8,%3csvg xmlns=%27http://www.w3.org/2000/svg%27 viewBox=%270 0 24 24%27 fill=%27none%27 stroke=%27currentColor%27 stroke-width=%272%27%3e%3cpath d=%27M6 9l6 6 6-6%27/%3e%3c/svg%3e')] bg-size-[1rem] bg-position-[right_0.5rem_center] bg-no-repeat pr-8`}
                    value={pendingFilters.agentId}
                    onChange={(e) => updatePending("agentId", e.target.value)}
                  >
                    <option value="">全部角色</option>
                    {agents.map((agent) => (
                      <option key={agent.id} value={agent.id}>
                        {agent.name}
                      </option>
                    ))}
                  </select>
                </div>

                {/* 操作按钮 */}
                <div className="flex gap-2 pt-1">
                  <button
                    type="button"
                    onClick={handleSearch}
                    className="flex-1 rounded-xl bg-moss px-4 py-2 text-sm font-medium text-white transition hover:bg-moss/90"
                  >
                    检索
                  </button>
                  <button
                    type="button"
                    onClick={handleReset}
                    className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm text-slate-600 transition hover:bg-slate-50"
                  >
                    重置
                  </button>
                </div>
              </div>
            </section>
          </div>
        </aside>

        {/* 右侧事件列表 */}
        <div className="flex min-h-0 flex-1 flex-col bg-white">
          {/* 世界时间信息 */}
          {timeline?.run_info && (
            <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <span className="h-1.5 w-1.5 rounded-full bg-moss/60" />
                世界时间 {simDayLabelFromIso(timeline.run_info.world_start_iso, timeline.run_info.current_world_time_iso)} {timeline.run_info.current_world_time_iso.substring(11, 16)}
                <span className="text-slate-300">·</span>
                每 Tick {timeline.run_info.tick_minutes} 分钟
              </div>
              {isRefreshing ? (
                <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-2.5 py-1 text-[11px] text-slate-500">
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-moss" />
                  刷新中
                </span>
              ) : null}
            </div>
          )}

          {/* 事件列表 */}
          <div ref={listContainerRef} className="flex-1 overflow-y-auto p-4">
            {loading ? (
              <div className="space-y-4">
                {Array.from({ length: 4 }).map((_, index) => (
                  <div key={index} className="rounded-2xl border border-slate-100 bg-slate-50/60 p-4">
                    <div className="mb-3 flex items-center gap-3">
                      <div className="h-6 w-20 animate-pulse rounded-lg bg-slate-200" />
                      <div className="h-4 w-40 animate-pulse rounded bg-slate-100" />
                    </div>
                    <div className="space-y-2">
                      {Array.from({ length: 3 }).map((__, innerIndex) => (
                        <div key={innerIndex} className="rounded-xl border border-white bg-white p-3 shadow-xs">
                          <div className="flex items-center gap-3">
                            <div className="h-8 w-8 animate-pulse rounded-full bg-slate-100" />
                            <div className="min-w-0 flex-1 space-y-2">
                              <div className="h-4 w-3/4 animate-pulse rounded bg-slate-100" />
                              <div className="h-3 w-1/3 animate-pulse rounded bg-slate-50" />
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            ) : error ? (
              <div className="flex h-64 items-center justify-center text-amber-600">
                ⚠️ {error}
              </div>
            ) : groups.length === 0 ? (
              <div className="flex h-64 items-center justify-center text-slate-400">
                暂无事件数据
              </div>
            ) : (
              <div className="space-y-4">
                {visibleGroups.map(([tick, events]) => (
                  <TickGroup
                    key={tick}
                    tick={Number(tick)}
                    events={events}
                    tickMinutes={timeline?.run_info?.tick_minutes ?? 5}
                    currentTick={timeline?.run_info?.current_tick ?? 0}
                    currentWorldTimeIso={timeline?.run_info?.current_world_time_iso}
                  />
                ))}
                {hasMoreGroups ? (
                  <div className="flex justify-center pt-2">
                    <div className="rounded-full bg-slate-100 px-3 py-1.5 text-xs text-slate-500">
                      继续下滑以加载更多时间段
                    </div>
                  </div>
                ) : null}
                {!hasMoreGroups && hasMoreEvents ? (
                  <div className="flex justify-center pt-2">
                    <div className="rounded-full bg-slate-100 px-3 py-1.5 text-xs text-slate-500">
                      {isLoadingMore ? "正在获取更早事件..." : "继续下滑以获取更早事件"}
                    </div>
                  </div>
                ) : null}
                {(hasMoreGroups || hasMoreEvents) ? <div ref={loadMoreRef} className="h-1 w-full" /> : null}
              </div>
            )}
          </div>
        </div>
      </div>
    </Modal>
  );
}

// ============================================================================
// Tick 分组组件
// ============================================================================

interface TickGroupProps {
  tick: number;
  events: TimelineEvent[];
  tickMinutes: number;
  currentTick: number;
  currentWorldTimeIso?: string;
}

function TickGroup({ tick, events, tickMinutes, currentTick, currentWorldTimeIso }: TickGroupProps) {
  return (
    <div className="rounded-2xl border border-slate-100 bg-slate-50/50 p-4">
      <div className="mb-3 flex items-center gap-3">
        <span className="rounded-lg bg-moss/10 px-2 py-1 text-xs font-medium text-moss">
          Tick {tick}
        </span>
        <span className="text-xs text-slate-400">
          {tickToSimDayTime(tick, tickMinutes, currentTick, currentWorldTimeIso)} · {events.length} 个事件
        </span>
      </div>
      <div className="space-y-2">
        {events.map((event) => (
          <EventCard key={event.id} event={event} />
        ))}
      </div>
    </div>
  );
}

// ============================================================================
// 事件卡片组件
// ============================================================================

interface EventCardProps {
  event: TimelineEvent;
}

function EventCard({ event }: EventCardProps) {
  const meta = getEventMeta(event.event_type);
  const description = describeTimelineEvent(event);
  const actorName = event.payload.actor_name;
  // 移动事件显示目的地，其他事件显示当前所在位置
  const locationName =
    event.event_type === "move"
      ? (event.payload.to_location_name ?? event.payload.location_name)
      : event.payload.location_name;

  return (
    <div className="rounded-xl border border-white bg-white p-3 shadow-xs transition hover:shadow-md">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="text-lg">{meta.icon}</span>
          <span className="text-sm font-medium text-ink">{description}</span>
        </div>
        <span
          className={`shrink-0 rounded-md px-2 py-0.5 text-[10px] ${
            meta.label === "对话"
              ? "bg-emerald-50 text-emerald-600"
              : meta.label === "移动"
                ? "bg-blue-50 text-blue-600"
                : meta.label === "工作"
                  ? "bg-amber-50 text-amber-600"
                  : meta.label === "休息"
                    ? "bg-slate-100 text-slate-600"
                    : "bg-violet-50 text-violet-600"
          }`}
        >
          {meta.label}
        </span>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        {typeof actorName === "string" && actorName && (
          <span className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-0.5 text-[11px] text-slate-600">
            <span className="h-1 w-1 rounded-full bg-slate-400" />
            {actorName}
          </span>
        )}
        {typeof locationName === "string" && locationName && (
          <span className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-0.5 text-[11px] text-slate-600">
            <span className="h-1 w-1 rounded-full bg-rose-400" />
            {locationName}
          </span>
        )}
        <span className="ml-auto text-[10px] text-slate-400">
          重要度 {event.importance ?? 0}
        </span>
      </div>
    </div>
  );
}
