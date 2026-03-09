"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Modal } from "@/components/modal";
import { getApiBaseUrl } from "@/lib/api";
import type { AgentSummary, TimelineEvent, TimelineResponse } from "@/lib/types";
import { describeTimelineEvent, getEventMeta } from "@/lib/event-utils";
import { simDayLabel } from "@/lib/world-utils";

const EVENT_TYPE_OPTIONS = [
  { value: "", label: "全部类型" },
  { value: "talk", label: "💬 对话" },
  { value: "move", label: "🚶 移动" },
  { value: "work", label: "⚒️ 工作" },
  { value: "rest", label: "😴 休息" },
  { value: "plan", label: "📋 计划" },
  { value: "reflect", label: "🔍 反思" },
  {
    value:
      "director_inject,director_broadcast,director_activity,director_shutdown,director_weather_change",
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

const PAGE_SIZE = 500;

interface TimelineModalProps {
  isOpen: boolean;
  onClose: () => void;
  runId: string;
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

function isoToDatetimeLocal(iso: string): string {
  return iso.substring(0, 16);
}

export function TimelineModal({ isOpen, onClose, runId }: TimelineModalProps) {
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [pendingFilters, setPendingFilters] = useState<Filters>(EMPTY_FILTERS);
  const [offset, setOffset] = useState(0);
  const [timeline, setTimeline] = useState<TimelineResponse | null>(null);
  const [agents, setAgents] = useState<AgentSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // 加载角色列表
  useEffect(() => {
    if (!isOpen) return;
    fetch(`${getApiBaseUrl()}/runs/${runId}/agents`, { headers: { Accept: "application/json" } })
      .then((r) => r.json())
      .then((data: { agents?: AgentSummary[] }) => setAgents(data.agents ?? []))
      .catch(() => setAgents([]));
  }, [runId, isOpen]);

  const fetchTimeline = useCallback(
    async (appliedFilters: Filters, currentOffset: number, orderDesc: boolean = true) => {
      setLoading(true);
      setError(null);
      try {
        const url = buildTimelineUrl(getApiBaseUrl(), runId, appliedFilters, PAGE_SIZE, currentOffset, orderDesc);
        const res = await fetch(url, { cache: "no-store", headers: { Accept: "application/json" } });
        if (!res.ok) throw new Error(`请求失败: ${res.status}`);
        const data = (await res.json()) as TimelineResponse;
        setTimeline(data);
      } catch (e) {
        setError(e instanceof Error ? e.message : "加载失败");
        setTimeline(null);
      } finally {
        setLoading(false);
      }
    },
    [runId],
  );

  // 打开时加载数据
  useEffect(() => {
    if (isOpen) {
      void fetchTimeline(EMPTY_FILTERS, 0);
    }
  }, [isOpen, fetchTimeline]);

  const handleSearch = () => {
    setFilters(pendingFilters);
    setOffset(0);
    void fetchTimeline(pendingFilters, 0);
  };

  const handleReset = () => {
    setPendingFilters(EMPTY_FILTERS);
    setFilters(EMPTY_FILTERS);
    setOffset(0);
    void fetchTimeline(EMPTY_FILTERS, 0);
  };

  const handlePrevPage = () => {
    const newOffset = Math.max(0, offset - PAGE_SIZE);
    setOffset(newOffset);
    void fetchTimeline(filters, newOffset);
  };

  const handleNextPage = () => {
    const newOffset = offset + PAGE_SIZE;
    setOffset(newOffset);
    void fetchTimeline(filters, newOffset);
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
  const totalPages = Math.ceil(total / PAGE_SIZE);
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1;

  const updatePending = (key: keyof Filters, value: string) =>
    setPendingFilters((prev) => ({ ...prev, [key]: value }));

  const inputCls =
    "w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-ink placeholder-slate-300 focus:border-moss focus:outline-none";
  const labelCls = "text-[11px] uppercase tracking-[0.15em] text-slate-400";

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      size="full"
      showCloseButton={false}
      title="🎬 事件回放"
      subtitle="按 tick 回放事件流，适合复盘剧情节点和角色行为链路"
    >
      <div className="flex min-h-0 flex-1 overflow-hidden">
        {/* 左侧过滤面板 */}
        <aside className="flex w-72 shrink-0 flex-col border-r border-slate-100 bg-slate-50/50">
          <div className="flex-1 overflow-y-auto p-4">
            {/* 摘要卡片 */}
            <section className="rounded-2xl border border-white/70 bg-white/80 p-4 shadow-sm backdrop-blur">
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
              {total > PAGE_SIZE && (
                <p className="mt-1 text-[10px] text-amber-600">
                  第 {currentPage}/{totalPages} 页
                </p>
              )}
            </section>

            {/* 搜索过滤 */}
            <section className="mt-3 rounded-2xl border border-white/70 bg-white/80 p-4 shadow-sm backdrop-blur">
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
                              {simDayLabel(Number(pendingFilters.tickFrom), timeline.run_info.tick_minutes)}
                            </span>
                          </div>
                        )}
                        {pendingFilters.tickTo && (
                          <div className="flex items-center gap-1">
                            <span>结束:</span>
                            <span className="text-moss">
                              {simDayLabel(Number(pendingFilters.tickTo), timeline.run_info.tick_minutes)}
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
                    className={`${inputCls} appearance-none bg-[url('data:image/svg+xml;charset=UTF-8,%3csvg xmlns=%27http://www.w3.org/2000/svg%27 viewBox=%270 0 24 24%27 fill=%27none%27 stroke=%27currentColor%27 stroke-width=%272%27%3e%3cpath d=%27M6 9l6 6 6-6%27/%3e%3c/svg%3e')] bg-[length:1rem] bg-[right_0.5rem_center] bg-no-repeat pr-8`}
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
                    className={`${inputCls} appearance-none bg-[url('data:image/svg+xml;charset=UTF-8,%3csvg xmlns=%27http://www.w3.org/2000/svg%27 viewBox=%270 0 24 24%27 fill=%27none%27 stroke=%27currentColor%27 stroke-width=%272%27%3e%3cpath d=%27M6 9l6 6 6-6%27/%3e%3c/svg%3e')] bg-[length:1rem] bg-[right_0.5rem_center] bg-no-repeat pr-8`}
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
                世界时间 {simDayLabel(timeline.run_info.current_tick, timeline.run_info.tick_minutes)} {timeline.run_info.current_world_time_iso.substring(11, 16)}
                <span className="text-slate-300">·</span>
                每 Tick {timeline.run_info.tick_minutes} 分钟
              </div>
            </div>
          )}

          {/* 事件列表 */}
          <div className="flex-1 overflow-y-auto p-4">
            {loading ? (
              <div className="flex h-64 items-center justify-center text-slate-400">
                <div className="mr-2 h-5 w-5 animate-spin rounded-full border-2 border-slate-200 border-t-moss" />
                加载中...
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
                {groups.map(([tick, events]) => (
                  <TickGroup
                    key={tick}
                    tick={Number(tick)}
                    events={events}
                    tickMinutes={timeline?.run_info?.tick_minutes ?? 5}
                  />
                ))}
              </div>
            )}
          </div>

          {/* 分页 */}
          {total > PAGE_SIZE && (
            <div className="flex items-center justify-between border-t border-slate-100 px-4 py-3">
              <button
                type="button"
                onClick={handlePrevPage}
                disabled={offset === 0}
                className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-600 transition hover:bg-slate-50 disabled:opacity-40"
              >
                上一页
              </button>
              <span className="text-sm text-slate-500">
                {currentPage} / {totalPages}
              </span>
              <button
                type="button"
                onClick={handleNextPage}
                disabled={currentPage >= totalPages}
                className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-600 transition hover:bg-slate-50 disabled:opacity-40"
              >
                下一页
              </button>
            </div>
          )}
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
}

function TickGroup({ tick, events, tickMinutes }: TickGroupProps) {
  return (
    <div className="rounded-2xl border border-slate-100 bg-slate-50/50 p-4">
      <div className="mb-3 flex items-center gap-3">
        <span className="rounded-lg bg-moss/10 px-2 py-1 text-xs font-medium text-moss">
          Tick {tick}
        </span>
        <span className="text-xs text-slate-400">
          {simDayLabel(tick, tickMinutes)} · {events.length} 个事件
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
  const meta = getEventMeta(event);
  const description = describeTimelineEvent(event);

  return (
    <div className="rounded-xl border border-white bg-white p-3 shadow-sm transition hover:shadow-md">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="text-lg">{meta.icon}</span>
          <span className="text-sm font-medium text-ink">{description}</span>
        </div>
        <span
          className={`shrink-0 rounded-md px-2 py-0.5 text-[10px] ${
            meta.badge === "对话"
              ? "bg-emerald-50 text-emerald-600"
              : meta.badge === "移动"
                ? "bg-blue-50 text-blue-600"
                : meta.badge === "工作"
                  ? "bg-amber-50 text-amber-600"
                  : meta.badge === "休息"
                    ? "bg-slate-100 text-slate-600"
                    : "bg-violet-50 text-violet-600"
          }`}
        >
          {meta.badge}
        </span>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        {event.agent_name && (
          <span className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-0.5 text-[11px] text-slate-600">
            <span className="h-1 w-1 rounded-full bg-slate-400" />
            {event.agent_name}
          </span>
        )}
        {event.location_name && (
          <span className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-0.5 text-[11px] text-slate-600">
            <span className="h-1 w-1 rounded-full bg-rose-400" />
            {event.location_name}
          </span>
        )}
        <span className="ml-auto text-[10px] text-slate-400">
          重要度 {event.importance ?? 0}
        </span>
      </div>
    </div>
  );
}
