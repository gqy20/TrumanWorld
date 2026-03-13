"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { getTimelineResult, listAgentsResult } from "@/lib/api";
import type { AgentSummary, TimelineEvent, TimelineFilter, TimelineResponse } from "@/lib/types";
import { describeTimelineEvent, getEventMeta } from "@/lib/event-utils";
import { simDayLabelFromIso } from "@/lib/world-utils";

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
  worldDatetimeFrom: string;  // YYYY-MM-DDTHH:MM
  worldDatetimeTo: string;    // YYYY-MM-DDTHH:MM
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

/** 将 ISO 字符串截取为 datetime-local input 所需的 YYYY-MM-DDTHH:MM 格式 */
function isoToDatetimeLocal(iso: string): string {
  // ISO 如 2026-03-02T07:00:00+00:00，取前 16 位即可
  return iso.substring(0, 16);
}

function toTimelineFilter(filters: Filters, offset: number, orderDesc = true): TimelineFilter {
  return {
    tick_from: filters.tickFrom ? Number(filters.tickFrom) : undefined,
    tick_to: filters.tickTo ? Number(filters.tickTo) : undefined,
    world_datetime_from: filters.worldDatetimeFrom || undefined,
    world_datetime_to: filters.worldDatetimeTo || undefined,
    event_type: filters.eventType || undefined,
    agent_id: filters.agentId || undefined,
    limit: PAGE_SIZE,
    offset,
    order_desc: orderDesc,
  };
}

const PAGE_SIZE = 250;

export default function TimelinePage() {
  const { runId } = useParams<{ runId: string }>();

  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [pendingFilters, setPendingFilters] = useState<Filters>(EMPTY_FILTERS);
  const [offset, setOffset] = useState(0);

  const [timeline, setTimeline] = useState<TimelineResponse | null>(null);
  const [agents, setAgents] = useState<AgentSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // 加载角色列表
  useEffect(() => {
    void listAgentsResult(runId)
      .then((result) => setAgents(result.data?.agents ?? []))
      .catch(() => setAgents([]));
  }, [runId]);

  const fetchTimeline = useCallback(
    async (appliedFilters: Filters, currentOffset: number, orderDesc: boolean = true) => {
      setLoading(true);
      setError(null);
      const result = await getTimelineResult(runId, toTimelineFilter(appliedFilters, currentOffset, orderDesc));
      if (result.data) {
        setTimeline(result.data);
      } else {
        setError(result.error === "network_error" ? "网络错误" : "加载失败");
        setTimeline(null);
      }
      setLoading(false);
    },
    [runId],
  );

  // 初始加载
  useEffect(() => {
    void fetchTimeline(EMPTY_FILTERS, 0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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

  // 将事件按 tick 分组，保持后端返回的顺序（后端已按倒序排列）
  const groups = useMemo(() => {
    if (!timeline) return [];
    const grouped: Record<number, TimelineEvent[]> = {};
    // 按后端返回的顺序插入，保持 tick 的倒序（最新的在前）
    for (const event of timeline.events) {
      (grouped[event.tick_no] ??= []).push(event);
    }
    // 将分组按 tick 倒序排列（最新的 tick 在前）
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
    "w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-ink placeholder-slate-300 focus:border-moss focus:outline-hidden";
  const labelCls = "text-[11px] uppercase tracking-[0.15em] text-slate-400";

  return (
    <div className="flex h-full flex-col overflow-hidden bg-[radial-gradient(circle_at_top,#f7f3e8,#eef5f1_48%,#f8fafc)]">
      {/* 顶部标题栏 */}
      <div className="border-b border-white/60 bg-white/65 px-8 py-5 backdrop-blur-sm">
        <Link href={`/runs/${runId}/world`} className="text-xs uppercase tracking-[0.25em] text-moss hover:text-ink">
          ← 返回 World Viewer
        </Link>
        <div className="mt-3 flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.24em] text-slate-400">Event Replay</p>
            <h1 className="mt-2 text-3xl font-semibold text-ink">Timeline</h1>
            <p className="mt-1 text-sm text-slate-500">按 tick 回放事件流，适合复盘剧情节点和角色行为链路。</p>
          </div>
          {timeline?.run_info && (
            <div className="flex items-center gap-2 rounded-full border border-white/70 bg-white/80 px-4 py-2 text-xs text-slate-600 shadow-xs">
              <span className="h-2 w-2 rounded-full bg-moss/60" />
              世界时间 {simDayLabelFromIso(timeline.run_info.world_start_iso, timeline.run_info.current_world_time_iso)} {timeline.run_info.current_world_time_iso.substring(11, 16)}
              <span className="text-slate-400">·</span>
              每 Tick {timeline.run_info.tick_minutes} 分钟
            </div>
          )}
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-8 py-6">
        <div className="grid gap-6 xl:grid-cols-[300px_minmax(0,1fr)]">
          {/* 左侧栏 */}
          <aside className="space-y-4 xl:sticky xl:top-6 xl:self-start xl:max-h-[calc(100vh-9rem)] xl:overflow-y-auto xl:pr-1">
            {/* 摘要卡片 */}
            <section className="rounded-[28px] border border-white/70 bg-white/80 p-5 shadow-xs backdrop-blur-sm">
              <p className="text-xs uppercase tracking-[0.22em] text-moss">回放摘要</p>
              <div className="mt-4 grid grid-cols-2 gap-2">
                <div className="rounded-2xl bg-mist px-3 py-3">
                  <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">数据库总事件</p>
                  <p className="mt-2 text-lg font-semibold text-ink">{total}</p>
                </div>
                <div className="rounded-2xl bg-mist px-3 py-3">
                  <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">当前页展示</p>
                  <p className="mt-2 text-lg font-semibold text-ink">{timeline?.events.length ?? 0}</p>
                </div>
                <div className="rounded-2xl bg-mist px-3 py-3">
                  <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">重要事件</p>
                  <p className="mt-2 text-lg font-semibold text-ink">{importantCount}</p>
                </div>
                <div className="rounded-2xl bg-mist px-3 py-3">
                  <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">Tick 组数</p>
                  <p className="mt-2 text-lg font-semibold text-ink">{groups.length}</p>
                </div>
              </div>
              {hasFilter && (
                <p className="mt-3 text-[11px] text-slate-400">
                  过滤后匹配 <span className="font-semibold text-moss">{filtered}</span> 条 / 共 {total} 条
                </p>
              )}
              {total > PAGE_SIZE && (
                <p className="mt-1 text-[11px] text-amber-600">
                  数据较多，当前第 {currentPage}/{totalPages} 页（每页 {PAGE_SIZE} 条）
                </p>
              )}
            </section>

            {/* 搜索过滤卡片 */}
            <section className="rounded-[28px] border border-white/70 bg-white/80 p-5 shadow-xs backdrop-blur-sm">
              <p className="text-xs uppercase tracking-[0.22em] text-moss">检索过滤</p>
              <div className="mt-4 space-y-4">

                {/* 世界日期时间范围 */}
                <div>
                  <label className={labelCls}>世界时间范围</label>
                  {timeline?.run_info && (
                    <p className="mt-0.5 text-[10px] text-slate-400">
                      世界起始 {isoToDatetimeLocal(timeline.run_info.world_start_iso).replace("T", " ")}
                      &nbsp;·&nbsp;
                      当前 {isoToDatetimeLocal(timeline.run_info.current_world_time_iso).replace("T", " ")}
                    </p>
                  )}
                  <div className="mt-1 space-y-1.5">
                    <input
                      type="datetime-local"
                      value={pendingFilters.worldDatetimeFrom}
                      min={timeline?.run_info ? isoToDatetimeLocal(timeline.run_info.world_start_iso) : undefined}
                      max={timeline?.run_info ? isoToDatetimeLocal(timeline.run_info.current_world_time_iso) : undefined}
                      onChange={(e) => updatePending("worldDatetimeFrom", e.target.value)}
                      className={inputCls}
                    />
                    <div className="flex items-center gap-1">
                      <span className="h-px flex-1 bg-slate-200" />
                      <span className="text-[10px] text-slate-400">至</span>
                      <span className="h-px flex-1 bg-slate-200" />
                    </div>
                    <input
                      type="datetime-local"
                      value={pendingFilters.worldDatetimeTo}
                      min={timeline?.run_info ? isoToDatetimeLocal(timeline.run_info.world_start_iso) : undefined}
                      max={timeline?.run_info ? isoToDatetimeLocal(timeline.run_info.current_world_time_iso) : undefined}
                      onChange={(e) => updatePending("worldDatetimeTo", e.target.value)}
                      className={inputCls}
                    />
                  </div>
                </div>

                {/* Tick 范围 */}
                <div>
                  <label className={labelCls}>Tick 范围</label>
                  <div className="mt-1 flex items-center gap-2">
                    <input
                      type="number"
                      min={0}
                      placeholder="起始"
                      value={pendingFilters.tickFrom}
                      onChange={(e) => updatePending("tickFrom", e.target.value)}
                      className={inputCls}
                    />
                    <span className="text-xs text-slate-400">—</span>
                    <input
                      type="number"
                      min={0}
                      placeholder="结束"
                      value={pendingFilters.tickTo}
                      onChange={(e) => updatePending("tickTo", e.target.value)}
                      className={inputCls}
                    />
                  </div>
                </div>

                {/* 事件类型 */}
                <div>
                  <label className={labelCls}>事件类型</label>
                  <select
                    value={pendingFilters.eventType}
                    onChange={(e) => updatePending("eventType", e.target.value)}
                    className={`mt-1 ${inputCls}`}
                  >
                    {EVENT_TYPE_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </div>

                {/* 角色下拉 */}
                <div>
                  <label className={labelCls}>角色</label>
                  <select
                    value={pendingFilters.agentId}
                    onChange={(e) => updatePending("agentId", e.target.value)}
                    className={`mt-1 ${inputCls}`}
                    disabled={agents.length === 0}
                  >
                    <option value="">全部角色</option>
                    {agents.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.name}{a.occupation ? ` · ${a.occupation}` : ""}
                      </option>
                    ))}
                  </select>
                  {agents.length === 0 && (
                    <p className="mt-1 text-[10px] text-slate-400">加载角色列表中…</p>
                  )}
                </div>

                {/* 操作按钮 */}
                <div className="flex gap-2 pt-1">
                  <button
                    onClick={handleSearch}
                    disabled={loading}
                    className="flex-1 rounded-xl bg-moss px-3 py-2 text-xs font-semibold text-white shadow-xs transition hover:bg-moss/90 disabled:opacity-50"
                  >
                    {loading ? "加载中…" : "检索"}
                  </button>
                  <button
                    onClick={handleReset}
                    disabled={loading}
                    className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600 transition hover:bg-slate-50 disabled:opacity-50"
                  >
                    重置
                  </button>
                </div>
              </div>
            </section>

            {/* 阅读提示 */}
            <section className="rounded-[28px] border border-slate-200 bg-white/80 p-5 shadow-xs">
              <p className="text-xs uppercase tracking-[0.22em] text-slate-400">阅读提示</p>
              <div className="mt-4 space-y-3 text-sm leading-6 text-slate-600">
                <p>先看最近 tick，再向下回溯，能更快定位一段行为链路是怎么发生的。</p>
                <p>导演注入和高重要度事件通常是剧情转折点，优先看这两类更高效。</p>
                <p>想确认空间位置时，返回 World Viewer 会更直观。</p>
              </div>
            </section>
          </aside>

          {/* 右侧主内容 */}
          <section className="rounded-[32px] border border-white/70 bg-white/78 p-5 shadow-xs backdrop-blur-sm">
            {loading ? (
              <div className="flex h-40 items-center justify-center text-sm text-slate-400">加载中…</div>
            ) : error ? (
              <div className="rounded-[28px] border border-red-200 bg-red-50 px-6 py-8 text-center text-sm text-red-600">
                {error}
              </div>
            ) : !timeline || timeline.events.length === 0 ? (
              <div className="rounded-[28px] border border-slate-200 bg-white px-6 py-16 text-center text-sm text-slate-500">
                {hasFilter
                  ? "当前过滤条件下没有匹配的事件，请调整检索条件。"
                  : "暂无事件。世界运行后，居民的行为和导演注入都会在这里出现。"}
              </div>
            ) : (
              <>
                <div className="space-y-6">
                  {groups.map(([tick, events]) => {
                    const tickNo = Number(tick);
                    // 取该 tick 组第一个事件的世界时间
                    const firstEvent = events[0];
                    const worldTime = firstEvent?.world_time;
                    // 从世界起始日期 + 该事件日期推算天数标签
                    const worldStartIso = timeline.run_info?.world_start_iso ?? "";
                    const eventDateIso = firstEvent?.world_date
                      ? `${firstEvent.world_date}T00:00:00Z`
                      : timeline.run_info?.current_world_time_iso ?? "";
                    const simDayStr = worldStartIso && eventDateIso
                      ? simDayLabelFromIso(worldStartIso, eventDateIso)
                      : `第${Math.floor(tickNo * (timeline.run_info?.tick_minutes ?? 5) / 1440) + 1}天`;

                    return (
                      <div key={tick} className="rounded-[28px] border border-slate-200 bg-white/85 p-4 shadow-xs">
                        <div className="mb-4 flex items-center gap-3 rounded-full bg-white/90 px-3 py-2">
                          <span className="rounded-full bg-moss/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.22em] text-moss">
                            Tick {tick}
                          </span>
                          <span className="flex items-center gap-1 rounded-full bg-slate-50 px-2.5 py-1 text-[11px] text-slate-500">
                            🕐 {simDayStr}{worldTime && ` ${worldTime}`}
                          </span>
                          <span className="text-xs text-slate-400">{events.length} 条事件</span>
                          <span className="h-px flex-1 bg-slate-200" />
                        </div>

                        <div className="space-y-3">
                          {events.map((event) => {
                            const meta = getEventMeta(event.event_type);
                            return (
                              <article
                                key={event.id}
                                className="rounded-[24px] border border-slate-200 bg-white px-4 py-4 shadow-xs"
                              >
                                <div className="flex items-start justify-between gap-3">
                                  <div className="flex items-start gap-3">
                                    <span className="flex h-10 w-10 items-center justify-center rounded-full bg-slate-50 text-lg shadow-xs">
                                      {meta.icon}
                                    </span>
                                    <div>
                                      <p className="text-sm font-medium leading-6 text-ink">
                                        {describeTimelineEvent(event)}
                                      </p>
                                      <div className="mt-2 flex flex-wrap gap-1.5">
                                        {event.payload.actor_name ? (
                                          <span className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-[11px] text-slate-600">
                                            {String(event.payload.actor_name)}
                                          </span>
                                        ) : null}
                                        {event.payload.target_name ? (
                                          <span className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-[11px] text-slate-600">
                                            {String(event.payload.target_name)}
                                          </span>
                                        ) : null}
                                        {event.payload.location_name ? (
                                          <span className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-[11px] text-slate-600">
                                            📍 {String(event.payload.location_name)}
                                          </span>
                                        ) : null}
                                      </div>
                                    </div>
                                  </div>

                                  <div className="flex flex-col items-end gap-1">
                                    <span className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${meta.chip}`}>
                                      {meta.label}
                                    </span>
                                    {event.importance != null ? (
                                      <span className="text-[11px] text-slate-400">重要度 {event.importance}</span>
                                    ) : null}
                                  </div>
                                </div>
                              </article>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })}
                </div>

                {/* 分页控制 */}
                {total > PAGE_SIZE && (
                  <div className="mt-6 flex items-center justify-between rounded-[24px] border border-slate-200 bg-white px-5 py-3">
                    <button
                      onClick={handlePrevPage}
                      disabled={offset === 0 || loading}
                      className="rounded-xl border border-slate-200 px-4 py-2 text-xs text-slate-600 transition hover:bg-slate-50 disabled:opacity-40"
                    >
                      ← 上一页
                    </button>
                    <span className="text-xs text-slate-500">
                      第 {currentPage} / {totalPages} 页（共 {total} 条）
                    </span>
                    <button
                      onClick={handleNextPage}
                      disabled={offset + PAGE_SIZE >= total || loading}
                      className="rounded-xl border border-slate-200 px-4 py-2 text-xs text-slate-600 transition hover:bg-slate-50 disabled:opacity-40"
                    >
                      下一页 →
                    </button>
                  </div>
                )}
              </>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
