"use client";

import { useMemo } from "react";
import Link from "next/link";
import type { WorldSnapshot } from "@/lib/types";
import { AgentAvatar } from "@/components/agent-avatar";
import { inferAgentStatus } from "@/lib/agent-utils";
import { EventCard } from "@/components/event-card";
import {
  beatBadge,
  buildWorldNameMaps,
  compressConversationDisplayEvents,
  locationBeat,
  tickToSimDayTime,
} from "@/lib/world-utils";
import { Modal } from "@/components/modal";

type LocationDetailModalProps = {
  isOpen: boolean;
  onClose: () => void;
  world: WorldSnapshot;
  locationId: string;
  onLocationChange: (locationId: string) => void;
  runId: string;
};

export function LocationDetailModal({
  isOpen,
  onClose,
  world,
  locationId,
  onLocationChange,
  runId,
}: LocationDetailModalProps) {
  const { agentNameMap, locationNameMap, locationEvents } = useMemo(() => {
    const { agentNameMap, locationNameMap } = buildWorldNameMaps(world);
    const events = world.recent_events
      .filter((event) => event.location_id === locationId)
      .sort((a, b) => b.tick_no - a.tick_no); // 按 tick 倒序，最新的在前
    const visibleEvents = compressConversationDisplayEvents(events);

    return {
      agentNameMap,
      locationNameMap,
      locationEvents: visibleEvents,
    };
  }, [world, locationId]);

  const location = world.locations.find((l) => l.id === locationId);
  const beat = location ? beatBadge(locationBeat(location.id, world.recent_events, world.locations, world.run.current_tick)) : null;
  const latestTick = locationEvents[0]?.tick_no ?? world.run.current_tick ?? 0;

  if (!isOpen || !location) return null;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      variant="panel"
      showCloseButton={false}
      title={location.name}
      headerActions={
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => {
              const currentIndex = world.locations.findIndex((l) => l.id === locationId);
              const prevIndex = currentIndex > 0 ? currentIndex - 1 : world.locations.length - 1;
              onLocationChange(world.locations[prevIndex].id);
            }}
            className="flex h-8 w-8 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-500 transition hover:border-moss hover:text-moss"
            title="上一个地点"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-4 w-4">
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <span className="px-2 text-xs text-slate-500">
            {world.locations.findIndex((l) => l.id === locationId) + 1} / {world.locations.length}
          </span>
          <button
            type="button"
            onClick={() => {
              const currentIndex = world.locations.findIndex((l) => l.id === locationId);
              const nextIndex = currentIndex < world.locations.length - 1 ? currentIndex + 1 : 0;
              onLocationChange(world.locations[nextIndex].id);
            }}
            className="flex h-8 w-8 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-500 transition hover:border-moss hover:text-moss"
            title="下一个地点"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-4 w-4">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
            </svg>
          </button>
        </div>
      }
    >

        <div className="grid grid-cols-3 gap-4 border-b border-slate-100 bg-slate-50/50 px-6 py-3">
          <div className="text-center">
            <p className="text-2xl font-semibold text-ink">{location.occupants.length}</p>
            <p className="text-xs text-slate-400">当前人数</p>
          </div>
          <div className="text-center">
            <p className="text-2xl font-semibold text-ink">{location.capacity}</p>
            <p className="text-xs text-slate-400">容量</p>
          </div>
          <div className="text-center">
            <p className="text-2xl font-semibold text-ink">{locationEvents.length}</p>
            <p className="text-xs text-slate-400">相关事件</p>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto">
          <div className="border-b border-slate-100 p-6">
            <div className="mb-3 flex items-center gap-2">
              <h3 className="text-sm font-medium text-ink">当前居民</h3>
              {beat && (
                <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${beat.cls}`}>
                  {beat.label}
                </span>
              )}
            </div>
            {location.occupants.length === 0 ? (
              <p className="rounded-2xl bg-slate-50 px-4 py-4 text-sm text-slate-500">
                这里暂时没有居民。
              </p>
            ) : (
              <div className="space-y-2">
                {location.occupants.map((agent) => (
                  <Link
                    key={agent.id}
                    href={`/runs/${runId}/agents/${agent.id}`}
                    onClick={onClose}
                    className="group flex items-center gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-3 transition hover:border-moss hover:shadow-xs"
                  >
                    <AgentAvatar
                      agentId={agent.id}
                      name={agent.name}
                      occupation={agent.occupation}
                      status={inferAgentStatus(agent.id, world.recent_events)}
                      size="md"
                      configId={agent.config_id}
                    />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-ink group-hover:text-moss">
                        {agent.name}
                      </p>
                      <p className="truncate text-xs text-slate-500">
                        {agent.current_goal ?? "暂无公开目标"}
                      </p>
                    </div>
                    <span className="text-xs text-slate-400">{agent.occupation ?? "居民"}</span>
                  </Link>
                ))}
              </div>
            )}
          </div>

          <div className="p-6">
            <h3 className="mb-3 text-sm font-medium text-ink">地点事件</h3>
            {locationEvents.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-8 text-slate-400">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-12 w-12">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                <p className="mt-3 text-sm">该地点暂无事件记录</p>
              </div>
            ) : (
              <div className="space-y-2">
                {locationEvents
                  .slice(0, world.health_metrics_config?.ui_location_detail_max_events ?? 50)
                  .map((event, index) => (
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
                {locationEvents.length > (world.health_metrics_config?.ui_location_detail_max_events ?? 50) && (
                  <p className="text-center text-xs text-slate-500">
                    还有 {locationEvents.length - (world.health_metrics_config?.ui_location_detail_max_events ?? 50)} 条事件
                  </p>
                )}
              </div>
            )}
          </div>
        </div>
    </Modal>
  );
}
