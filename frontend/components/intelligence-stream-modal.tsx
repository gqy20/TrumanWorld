"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence } from "framer-motion";
import type { WorldSnapshot, WorldEvent } from "@/lib/types";
import { EventCard } from "@/components/event-card";
import {
  buildWorldNameMaps,
  compressConversationDisplayEvents,
  filterWorldEvents,
  tickToSimDayTime,
  type EventFilter,
} from "@/lib/world-utils";
import { getRunEventsResult } from "@/lib/api";
import { EVENT_FILTERS } from "@/lib/constants";
import { LoadingState } from "@/components/loading-state";
import { ErrorState } from "@/components/error-state";
import { Modal, WorkspaceModalShell } from "@/components/modal";

type LocationFilter = string | null;

type IntelligenceStreamModalProps = {
  isOpen: boolean;
  onClose: () => void;
  world: WorldSnapshot;
  runId: string;
  maxEvents?: number;
  pollIntervalMs?: number;
};

const DEFAULT_MAX_EVENTS = 500;
const MAX_TRACKED_EVENT_IDS = 1000;

export function IntelligenceStreamModal({
  isOpen,
  onClose,
  world,
  runId,
  maxEvents,
  pollIntervalMs,
}: IntelligenceStreamModalProps) {
  const [eventFilter, setEventFilter] = useState<EventFilter>("all");
  const [locationFilter, setLocationFilter] = useState<LocationFilter>(null);

  const [allEvents, setAllEvents] = useState<WorldEvent[]>(world.recent_events);
  // Track known event ids to avoid replacing the whole list on every poll tick
  const knownIdsRef = useRef<Set<string>>(new Set(world.recent_events.map((e) => e.id)));
  // Track latest tick for incremental queries
  const latestTickRef = useRef<number>(0);
  const [isLoading, setIsLoading] = useState(false);
  const [loadError, setLoadError] = useState(false);
  // Prevent duplicate in-flight requests within the same open session
  const isLoadingRef = useRef(false);
  const eventLimit = maxEvents ?? DEFAULT_MAX_EVENTS;

  const trimKnownIds = useCallback((events: WorldEvent[]) => {
    knownIdsRef.current = new Set(events.slice(0, MAX_TRACKED_EVENT_IDS).map((event) => event.id));
  }, []);

  const loadAllEvents = useCallback(async (force = false) => {
    if (!force && isLoadingRef.current) return;
    isLoadingRef.current = true;
    // Only show full loading spinner on first open (knownIds empty = first load)
    const isFirstLoad = knownIdsRef.current.size === 0;
    if (isFirstLoad) setIsLoading(true);
    setLoadError(false);
    // Incremental query: pass since_tick for non-first loads (unless forced)
    const sinceTick = force ? undefined : (isFirstLoad ? undefined : latestTickRef.current);
    const result = await getRunEventsResult(runId, undefined, eventLimit, sinceTick);
    if (isFirstLoad) setIsLoading(false);
    isLoadingRef.current = false;
    if (result.data) {
      const incoming = result.data.events;
      // Update latest tick from response for next incremental query
      if (result.data.latest_tick != null) {
        latestTickRef.current = result.data.latest_tick;
      }
      // Only update state when there are genuinely new events to avoid re-render flicker
      const newEvents = incoming.filter((e) => !knownIdsRef.current.has(e.id));
      if (newEvents.length > 0 || knownIdsRef.current.size === 0) {
        setAllEvents((current) => {
          const merged = force ? incoming : [...incoming, ...current];
          const deduped: WorldEvent[] = [];
          const seen = new Set<string>();
          for (const event of merged) {
            if (seen.has(event.id)) continue;
            seen.add(event.id);
            deduped.push(event);
            if (deduped.length >= eventLimit) break;
          }
          trimKnownIds(deduped);
          return deduped;
        });
      }
    } else {
      setLoadError(true);
      // Fall back to latest world snapshot events
      if (knownIdsRef.current.size === 0) {
        const fallbackEvents = world.recent_events.slice(0, eventLimit);
        trimKnownIds(fallbackEvents);
        setAllEvents(fallbackEvents);
      }
    }
  }, [eventLimit, runId, trimKnownIds, world.recent_events]);

  // Reset known-ids and latest tick whenever the modal is freshly opened so a full reload occurs
  const prevIsOpenRef = useRef(false);
  useEffect(() => {
    if (isOpen && !prevIsOpenRef.current) {
      // Fresh open: clear cache so first poll does a full replace
      knownIdsRef.current = new Set();
      latestTickRef.current = 0;
      setAllEvents(world.recent_events.slice(0, eventLimit));
    } else if (!isOpen && prevIsOpenRef.current) {
      knownIdsRef.current = new Set();
      latestTickRef.current = 0;
      setAllEvents([]);
    }
    prevIsOpenRef.current = isOpen;
  }, [eventLimit, isOpen, world.recent_events]);

  // Reload every time the modal is opened so new ticks are always reflected;
  // also poll every 5 s while open so live events appear without re-opening.
  useEffect(() => {
    if (!isOpen) return;
    loadAllEvents();
    const timer = setInterval(() => loadAllEvents(), pollIntervalMs ?? 5000);
    return () => clearInterval(timer);
  }, [isOpen, loadAllEvents, pollIntervalMs]);

  const { agentNameMap, locationNameMap, visibleEvents, latestTick } = useMemo(() => {
    const { agentNameMap, locationNameMap } = buildWorldNameMaps(world);
    const filtered = filterWorldEvents(allEvents, eventFilter, locationFilter);
    const visibleEvents = compressConversationDisplayEvents(filtered);
    const tick = allEvents[0]?.tick_no ?? world.run.current_tick ?? 0;
    return { agentNameMap, locationNameMap, visibleEvents, latestTick: tick };
  }, [eventFilter, locationFilter, world, allEvents]);

  if (!isOpen) return null;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      variant="workspace"
      title="世界情报流"
      subtitle="实时事件监控中心"
    >
      <WorkspaceModalShell
        toolbar={
          <div className="flex flex-wrap items-center gap-2">
          <div className="flex gap-1">
            {EVENT_FILTERS.map((filter) => {
              const active = filter.id === eventFilter;
              return (
                <button
                  key={filter.id}
                  type="button"
                  onClick={() => setEventFilter(filter.id)}
                  className={`rounded-full px-3 py-1.5 text-xs transition ${
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
          <div className="h-4 w-px bg-slate-200" />
          <div className="flex flex-wrap gap-1">
            <button
              type="button"
              onClick={() => setLocationFilter(null)}
              className={`rounded-full px-3 py-1.5 text-xs transition ${
                locationFilter === null
                  ? "bg-moss text-white"
                  : "border border-slate-200 bg-white text-slate-500 hover:border-moss hover:text-moss"
              }`}
            >
              全部地点
            </button>
            {world.locations.map((loc) => (
              <button
                key={loc.id}
                type="button"
                onClick={() => setLocationFilter(loc.id === locationFilter ? null : loc.id)}
                className={`rounded-full px-3 py-1.5 text-xs transition ${
                  locationFilter === loc.id
                    ? "border border-moss/40 bg-moss/20 text-moss"
                    : "border border-slate-200 bg-white text-slate-500 hover:border-moss hover:text-moss"
                }`}
              >
                {loc.name}
              </button>
            ))}
          </div>
          </div>
        }
        footer={
          <div className="flex items-center justify-between text-sm text-slate-500">
            <span>
              显示 {visibleEvents.length} 条
              {eventFilter !== "all" || locationFilter ? (
                <span className="ml-1 text-slate-400">（已筛选 / 共 {allEvents.length} 条）</span>
              ) : null}
            </span>
            <button
              type="button"
              onClick={() => {
                onClose();
                window.dispatchEvent(new CustomEvent("openTimelineModal"));
              }}
              className="text-moss hover:underline"
            >
              查看完整时间线 →
            </button>
          </div>
        }
        contentClassName="overflow-y-auto bg-slate-50/30 p-6"
      >
        <div className="grid grid-cols-4 gap-4 rounded-2xl border border-slate-100 bg-slate-50/70 px-4 py-3">
          {[
            { label: "全量事件", value: allEvents.length },
            { label: "当前 Tick", value: world.run.current_tick ?? 0 },
            { label: "活跃地点", value: world.locations.filter((location) => location.occupants.length > 0).length },
            { label: "居民总数", value: world.locations.reduce((sum, location) => sum + location.occupants.length, 0) },
          ].map(({ label, value }) => (
            <div key={label} className="text-center">
              <p className="text-2xl font-semibold text-ink">{value}</p>
              <p className="text-xs text-slate-400">{label}</p>
            </div>
          ))}
        </div>
        <div className="mt-4">
          {isLoading ? (
            <LoadingState message="加载全量事件中..." size="sm" />
          ) : loadError ? (
            <ErrorState
              message="加载失败"
              onRetry={() => loadAllEvents(true)}
              size="sm"
            />
          ) : visibleEvents.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center text-slate-400">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-12 w-12">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <p className="mt-3 text-sm">当前筛选条件下没有事件</p>
            </div>
          ) : (
            <div className="space-y-3">
              <AnimatePresence mode="popLayout">
                {visibleEvents.map((event, index) => (
                  <EventCard
                    key={event.id}
                    event={event}
                    index={index}
                    isLatest={event.tick_no === latestTick}
                    agentNameMap={agentNameMap}
                    locationNameMap={locationNameMap}
                    simTime={tickToSimDayTime(
                      event.tick_no,
                      world.run.tick_minutes ?? 5,
                      world.run.current_tick ?? 0,
                      world.world_clock?.iso,
                    )}
                  />
                ))}
              </AnimatePresence>
            </div>
          )}
        </div>
      </WorkspaceModalShell>
    </Modal>
  );
}
