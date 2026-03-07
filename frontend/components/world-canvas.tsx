"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import useSWR from "swr";
import type { WorldSnapshot } from "@/lib/api";
import { AgentAvatar, inferAgentStatus } from "@/components/agent-avatar";
import { EventCard } from "@/components/event-card";
import { TownMap } from "@/components/town-map";

type WorldEvent = WorldSnapshot["recent_events"][number];
type EventFilter = "all" | "social" | "activity" | "movement";

const EVENT_FILTERS: Array<{ id: EventFilter; label: string }> = [
  { id: "all", label: "全部事件" },
  { id: "social", label: "对话" },
  { id: "activity", label: "动作" },
  { id: "movement", label: "移动" },
];

const API_BASE =
  (typeof window !== "undefined" ? process.env.NEXT_PUBLIC_API_BASE_URL : undefined) ??
  "http://127.0.0.1:8000/api";

async function worldFetcher(url: string): Promise<WorldSnapshot | null> {
  const response = await fetch(url, { headers: { Accept: "application/json" } });
  if (!response.ok) {
    throw new Error(`Failed to load world snapshot: ${response.status}`);
  }
  return response.json() as Promise<WorldSnapshot>;
}

function locationTone(locationType: string, highlighted: boolean) {
  const base = highlighted ? "ring-2 ring-moss/40 shadow-md" : "";
  if (locationType === "cafe") return `border-amber-200 bg-amber-50 ${base}`;
  if (locationType === "plaza") return `border-sky-200 bg-sky-50 ${base}`;
  if (locationType === "park") return `border-emerald-200 bg-emerald-50 ${base}`;
  if (locationType === "shop") return `border-violet-200 bg-violet-50 ${base}`;
  if (locationType === "home") return `border-pink-200 bg-pink-50 ${base}`;
  return `border-slate-200 bg-white ${base}`;
}

function eventMatchesFilter(event: WorldEvent, filter: EventFilter) {
  if (filter === "all") return true;
  if (filter === "social") return event.event_type === "talk";
  if (filter === "movement") return event.event_type === "move";
  return event.event_type === "work" || event.event_type === "rest";
}

function locationBeat(locationId: string, events: WorldSnapshot["recent_events"]) {
  const latest = events.find((event) => event.location_id === locationId);
  if (!latest) return "quiet";
  if (latest.event_type === "talk") return "conversation";
  if (latest.event_type === "move") return "arrival";
  if (latest.event_type === "work") return "working";
  if (latest.event_type === "rest") return "resting";
  return "quiet";
}

function beatBadge(beat: string) {
  const map: Record<string, { cls: string; label: string }> = {
    conversation: { cls: "bg-rose-100 text-rose-900", label: "对话中" },
    arrival: { cls: "bg-emerald-100 text-emerald-900", label: "有人抵达" },
    working: { cls: "bg-amber-100 text-amber-900", label: "工作中" },
    resting: { cls: "bg-slate-100 text-slate-800", label: "休息中" },
    quiet: { cls: "bg-white/80 text-slate-500", label: "安静" },
  };
  return map[beat] ?? { cls: "bg-mist text-slate-700", label: beat };
}

function formatGoal(goal?: string) {
  if (!goal) {
    return "暂无公开目标";
  }
  return goal.length > 28 ? `${goal.slice(0, 28)}...` : goal;
}

function formatSimTime(world: WorldSnapshot) {
  const tickMinutes = world.run.tick_minutes ?? 5;
  const totalMinutes = (world.run.current_tick ?? 0) * tickMinutes;
  const hours = Math.floor(totalMinutes / 60)
    .toString()
    .padStart(2, "0");
  const minutes = (totalMinutes % 60).toString().padStart(2, "0");
  return `${hours}:${minutes}`;
}

type Props = {
  runId: string;
  initialData?: WorldSnapshot | null;
};

export function WorldCanvas({ runId, initialData }: Props) {
  const router = useRouter();
  const [highlightedLocationId, setHighlightedLocationId] = useState<string | null>(null);
  const [eventFilter, setEventFilter] = useState<EventFilter>("all");

  const { data: world, error, isValidating, mutate } = useSWR<WorldSnapshot | null>(
    `${API_BASE}/runs/${runId}/world`,
    worldFetcher,
    {
      fallbackData: initialData ?? null,
      refreshInterval: (snapshot) => (snapshot?.run.status === "running" ? 5000 : 0),
      revalidateOnFocus: true,
    },
  );

  const latestTick = world?.recent_events[0]?.tick_no ?? world?.run.current_tick ?? 0;

  const { agentNameMap, locationNameMap, visibleEvents, activeConversations, activeLocations } =
    useMemo(() => {
      const namesByAgent: Record<string, string> = {};
      const namesByLocation: Record<string, string> = {};

      if (!world) {
        return {
          agentNameMap: namesByAgent,
          locationNameMap: namesByLocation,
          visibleEvents: [] as WorldEvent[],
          activeConversations: 0,
          activeLocations: 0,
        };
      }

      for (const location of world.locations) {
        namesByLocation[location.id] = location.name;
        for (const agent of location.occupants) {
          namesByAgent[agent.id] = agent.name;
        }
      }

      const filtered = world.recent_events.filter((event) => eventMatchesFilter(event, eventFilter));
      const conversationCount = world.recent_events.filter((event) => event.event_type === "talk").length;
      const activeLocationCount = world.locations.filter((location) =>
        world.recent_events.some((event) => event.location_id === location.id),
      ).length;

      return {
        agentNameMap: namesByAgent,
        locationNameMap: namesByLocation,
        visibleEvents: filtered,
        activeConversations: conversationCount,
        activeLocations: activeLocationCount,
      };
    }, [eventFilter, world]);

  if (!world) {
    return (
      <div className="rounded-3xl border border-slate-200 bg-white/80 p-8 text-center text-sm text-slate-500">
        未获取到世界快照，可能是后端未启动或 run 不存在。
      </div>
    );
  }

  const isRunning = world.run.status === "running";

  return (
    <div className="flex h-full min-h-[calc(100vh-11rem)] flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <span className="flex items-center gap-2 rounded-full bg-white/80 px-4 py-2 text-sm text-slate-700 shadow-sm">
          <span
            className={`h-2 w-2 rounded-full ${isValidating ? "animate-pulse bg-moss" : isRunning ? "bg-emerald-500" : "bg-slate-300"}`}
          />
          Tick {world.run.current_tick ?? 0} · {world.run.status}
        </span>
        <span className="rounded-full bg-white/40 px-3 py-2 text-xs text-slate-500">
          {isRunning ? "每 5 秒自动更新" : "当前已暂停自动轮询"}
        </span>
        <button
          type="button"
          onClick={() => void mutate()}
          className="rounded-full border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600 transition hover:border-moss hover:text-moss"
        >
          立即刷新
        </button>
        {error ? (
          <span className="rounded-full border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">
            最近一次刷新失败，已保留上一份快照
          </span>
        ) : null}
      </div>

      <div className="grid min-h-0 flex-1 gap-4 xl:grid-cols-[minmax(0,1.65fr)_minmax(420px,1fr)]">
        <div className="grid min-h-0 gap-4 xl:grid-rows-[minmax(380px,0.95fr)_minmax(0,1fr)]">
          <TownMap
            world={world}
            agentNameMap={agentNameMap}
            highlightedLocationId={highlightedLocationId}
            onLocationClick={(locationId) => {
              setHighlightedLocationId(locationId);
              const element = document.getElementById(`location-${locationId}`);
              element?.scrollIntoView({ behavior: "smooth", block: "center" });
            }}
            onAgentClick={(agentId) => {
              router.push(`/runs/${runId}/agents/${agentId}`);
            }}
          />

          <div className="min-h-0 rounded-3xl border border-slate-200 bg-white/70 p-4 shadow-sm">
            <div className="mb-3 flex items-center justify-between gap-3">
              <h2 className="text-lg font-semibold text-ink">地点卡片</h2>
              <span className="text-xs text-slate-400">地图与卡片联动高亮</span>
            </div>
            <div className="grid max-h-full auto-rows-[auto] gap-4 overflow-auto pr-1 md:grid-cols-2">
              <AnimatePresence mode="popLayout">
                {world.locations.map((location) => {
                  const beat = locationBeat(location.id, world.recent_events);
                  const badge = beatBadge(beat);
                  const highlighted = location.id === highlightedLocationId;

                  return (
                    <motion.div
                      id={`location-${location.id}`}
                      key={location.id}
                      layout
                      initial={{ opacity: 0, y: 12 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ type: "spring", stiffness: 260, damping: 24 }}
                      className={`relative rounded-3xl border px-5 py-5 shadow-sm transition ${locationTone(location.location_type, highlighted)}`}
                    >
                      <div className="pointer-events-none absolute right-4 top-4 h-20 w-20 rounded-full bg-white/35 blur-2xl" />

                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <h2 className="text-xl font-semibold text-ink">{location.name}</h2>
                          <p className="mt-0.5 text-xs uppercase tracking-[0.18em] text-slate-500">
                            {location.location_type}
                          </p>
                        </div>
                        <div className="rounded-full bg-white/80 px-3 py-1 text-xs font-medium text-slate-600">
                          {location.occupants.length}/{location.capacity}
                        </div>
                      </div>

                      <div className="mt-3 flex flex-wrap items-center gap-2">
                        <span className={`inline-block rounded-full px-3 py-1 text-xs font-medium ${badge.cls}`}>
                          {badge.label}
                        </span>
                        {highlighted ? (
                          <span className="rounded-full bg-moss/10 px-3 py-1 text-xs font-medium text-moss">
                            地图已聚焦
                          </span>
                        ) : null}
                      </div>

                      <div className="mt-4 space-y-2">
                        {location.occupants.length === 0 ? (
                          <p className="text-sm text-slate-400">这里暂时没有居民。</p>
                        ) : (
                          <AnimatePresence>
                            {location.occupants.map((agent) => (
                              <motion.div
                                key={agent.id}
                                layout
                                initial={{ opacity: 0, scale: 0.93 }}
                                animate={{ opacity: 1, scale: 1 }}
                                exit={{ opacity: 0, scale: 0.9 }}
                                transition={{ type: "spring", stiffness: 300, damping: 28 }}
                              >
                                <Link
                                  href={`/runs/${runId}/agents/${agent.id}`}
                                  className="group flex items-center gap-3 rounded-2xl border border-white/60 bg-white/70 px-3 py-2.5 transition hover:border-moss hover:bg-white hover:shadow-md"
                                >
                                  <AgentAvatar
                                    agentId={agent.id}
                                    name={agent.name}
                                    occupation={agent.occupation}
                                    status={inferAgentStatus(agent.id, world.recent_events)}
                                    size="sm"
                                  />
                                  <div className="min-w-0 flex-1">
                                    <p className="truncate font-medium text-ink transition-colors group-hover:text-moss">
                                      {agent.name}
                                    </p>
                                    <p className="truncate text-xs text-slate-500">{formatGoal(agent.current_goal)}</p>
                                  </div>
                                  <span className="flex-shrink-0 text-xs uppercase tracking-wide text-slate-400">
                                    {agent.occupation ?? "居民"}
                                  </span>
                                </Link>
                              </motion.div>
                            ))}
                          </AnimatePresence>
                        )}
                      </div>
                    </motion.div>
                  );
                })}
              </AnimatePresence>
            </div>
          </div>
        </div>

        <div className="grid min-h-0 gap-4 xl:grid-rows-[auto_auto_minmax(0,1fr)]">
          <div className="rounded-2xl border border-slate-200 bg-white/80 p-4 shadow-sm">
            <div className="flex items-center justify-between">
              <div className="text-xs uppercase tracking-[0.22em] text-moss">小镇概况</div>
              <span className="text-xs text-slate-400">{formatSimTime(world)}</span>
            </div>
            <div className="mt-3 grid grid-cols-3 gap-2">
              {[
                { label: "地点", value: world.locations.length },
                {
                  label: "居民",
                  value: world.locations.reduce((count, location) => count + location.occupants.length, 0),
                },
                { label: "活跃", value: activeLocations },
                { label: "对话", value: activeConversations },
                { label: "Tick", value: latestTick },
                { label: "状态", value: world.run.status === "running" ? "运行中" : "暂停" },
              ].map(({ label, value }) => (
                <motion.div
                  key={label}
                  layout
                  className="rounded-xl bg-mist px-2 py-2 text-center"
                >
                  <motion.div
                    key={`${label}-${String(value)}`}
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    className="text-lg font-semibold text-ink"
                  >
                    {value}
                  </motion.div>
                  <div className="text-[10px] uppercase tracking-wide text-slate-500">{label}</div>
                </motion.div>
              ))}
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white/60 p-3">
            <div className="flex items-start gap-2 text-xs text-slate-500">
              <span className="text-moss">💡</span>
              <p>点击地图地点可高亮对应卡片，暂停时自动停止轮询</p>
            </div>
          </div>

          <div className="flex min-h-0 flex-col rounded-2xl border border-slate-200 bg-white/80 p-4 shadow-sm">
            <div className="mb-2 flex items-center justify-between gap-2">
              <h2 className="text-sm font-semibold text-ink">近期事件</h2>
              <div className="flex gap-1">
                {EVENT_FILTERS.map((filter) => {
                  const active = filter.id === eventFilter;
                  return (
                    <button
                      key={filter.id}
                      type="button"
                      onClick={() => setEventFilter(filter.id)}
                      className={`rounded-full px-2.5 py-1 text-[11px] transition ${
                        active
                          ? "bg-ink text-white"
                          : "border border-slate-200 bg-white text-slate-500 hover:border-moss hover:text-moss"
                      }`}
                    >
                      {filter.label}
                    </button>
                  );
                })}
              </div>
            </div>
            <div className="min-h-0 space-y-2 overflow-auto pr-1">
              {visibleEvents.length === 0 ? (
                <p className="text-sm text-slate-500">当前筛选条件下没有公开事件。</p>
              ) : (
                <AnimatePresence mode="popLayout">
                  {visibleEvents.map((event, index) => (
                    <EventCard
                      key={event.id}
                      event={event}
                      index={index}
                      isLatest={event.tick_no === latestTick}
                      agentNameMap={agentNameMap}
                      locationNameMap={locationNameMap}
                    />
                  ))}
                </AnimatePresence>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
