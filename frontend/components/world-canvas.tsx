"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { AgentAvatar } from "@/components/agent-avatar";
import { TownMap } from "@/components/town-map";
import { inferAgentStatus } from "@/lib/agent-utils";
import { IntelligenceStreamModal } from "@/components/intelligence-stream-modal";
import { LocationDetailModal } from "@/components/location-detail-modal";
import { WorldHealthPanel } from "@/components/world-health-panel";
import { StoryTimeline } from "@/components/story-timeline";
import { TimelineModal } from "@/components/timeline-modal";
import { AgentDetailModal } from "@/components/agent-detail-modal";
import { useWorld } from "@/components/world-context";
import {
  calculateWorldHealthMetrics,
  aggregateStoryChapters,
} from "@/lib/world-insights";
import {
  beatBadge,
  buildWorldNameMaps,
  formatGoal,
  locationBeat,
  locationTone,
} from "@/lib/world-utils";

type Props = {
  runId: string;
};

export function WorldCanvas({ runId }: Props) {
  const { world } = useWorld();
  const [highlightedLocationId, setHighlightedLocationId] = useState<string | null>(null);
  const [isStreamExpanded, setIsStreamExpanded] = useState(false);
  const [isLocationExpanded, setIsLocationExpanded] = useState(false);
  const [isTimelineExpanded, setIsTimelineExpanded] = useState(false);
  const [isAgentExpanded, setIsAgentExpanded] = useState(false);
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);

  // 监听打开时间线弹窗的事件
  useEffect(() => {
    const handleOpenTimeline = () => setIsTimelineExpanded(true);
    window.addEventListener("openTimelineModal", handleOpenTimeline);
    return () => window.removeEventListener("openTimelineModal", handleOpenTimeline);
  }, []);

  // 计算世界洞察数据
  const { healthMetrics, storyChapters } = useMemo(() => {
    if (!world) {
      return { healthMetrics: null, storyChapters: [] };
    }
    return {
      healthMetrics: calculateWorldHealthMetrics(world),
      storyChapters: aggregateStoryChapters(world),
    };
  }, [world]);

  useEffect(() => {
    if (!world || world.locations.length === 0) {
      return;
    }
    setHighlightedLocationId((current) =>
      current && world.locations.some((location) => location.id === current) ? current : world.locations[0].id,
    );
  }, [world]);

  const { agentNameMap } = useMemo(() => {
    if (!world) {
      return {
        agentNameMap: {} as Record<string, string>,
      };
    }

    const { agentNameMap } = buildWorldNameMaps(world);
    return {
      agentNameMap,
    };
  }, [world]);

  if (!world) {
    return (
      <div className="rounded-3xl border border-slate-200 bg-white/80 p-8 text-center text-sm text-slate-500">
        未获取到世界快照，可能是后端未启动或 run 不存在。
      </div>
    );
  }

  const selectedLocation =
    world.locations.find((location) => location.id === highlightedLocationId) ?? world.locations[0] ?? null;
  const selectedLocationBeat = selectedLocation ? beatBadge(locationBeat(selectedLocation.id, world.recent_events, world.locations, world.run.current_tick)) : null;
  return (
    <div className="flex h-full min-h-0 flex-col gap-4">
      <div className="grid h-full min-h-0 gap-4 xl:grid-cols-[minmax(0,1fr)_320px_320px]">
        <div className="h-full min-h-[460px]">
          <TownMap
            world={world}
            agentNameMap={agentNameMap}
            highlightedLocationId={highlightedLocationId}
            onLocationClick={(locationId) => {
              setHighlightedLocationId(locationId);
            }}
            onAgentClick={(agentId) => {
              setSelectedAgentId(agentId);
              setIsAgentExpanded(true);
            }}
          />
        </div>

        {/* 中间列：世界健康度 + 地点详情 */}
        <div className="flex min-h-0 flex-col gap-4 overflow-auto">
          {/* 世界健康度面板 */}
          {healthMetrics && <WorldHealthPanel metrics={healthMetrics} runId={runId} world={world} />}

          {/* 地点详情卡片 */}
          <div className="rounded-[28px] border border-slate-200 bg-white/80 p-4 shadow-xs">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <h2 className="text-base font-semibold text-ink">{selectedLocation?.name ?? "暂无地点"}</h2>
                {selectedLocation && (
                  <span className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${locationTone(selectedLocation.location_type)}`}>
                    {selectedLocation.occupants.length} / {selectedLocation.capacity} 人
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2">
                {selectedLocationBeat ? (
                  <span className={`rounded-full px-3 py-1 text-xs font-medium ${selectedLocationBeat.cls}`}>
                    {selectedLocationBeat.label}
                  </span>
                ) : null}
                <button
                  type="button"
                  onClick={() => setIsLocationExpanded(true)}
                  className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-400 shadow-xs transition hover:border-moss hover:text-moss"
                  title="放大查看地点详情"
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-3.5 w-3.5">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
                  </svg>
                </button>
              </div>
            </div>

            {selectedLocation ? (
              <div className="mt-4 space-y-2">
                {selectedLocation.occupants.length === 0 ? (
                  <p className="rounded-2xl bg-slate-50 px-4 py-4 text-sm text-slate-500">这里暂时没有居民。</p>
                ) : (
                    selectedLocation.occupants.map((agent) => (
                      <Link
                        key={agent.id}
                        href={`/runs/${runId}/agents/${agent.id}`}
                        className="group flex items-center gap-3 rounded-2xl border border-slate-200 bg-white px-3 py-3 transition hover:border-moss hover:shadow-xs"
                      >
                        <AgentAvatar
                          agentId={agent.id}
                          name={agent.name}
                          occupation={agent.occupation}
                          status={inferAgentStatus(agent.id, world.recent_events)}
                          size="sm"
                          configId={agent.config_id}
                        />
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-medium text-ink group-hover:text-moss">{agent.name}</p>
                          <p className="truncate text-xs text-slate-500">{formatGoal(agent.current_goal)}</p>
                        </div>
                        <span className="text-[10px] uppercase tracking-[0.18em] text-slate-400">
                          {agent.occupation ?? "居民"}
                        </span>
                      </Link>
                    ))
                  )}
                </div>
            ) : null}
          </div>

          {/* 保留情报流模态框功能 */}
          {world && (
            <IntelligenceStreamModal
              isOpen={isStreamExpanded}
              onClose={() => setIsStreamExpanded(false)}
              world={world}
              runId={runId}
              maxEvents={world.health_metrics_config?.ui_intelligence_stream_max_events}
              pollIntervalMs={world.health_metrics_config?.ui_intelligence_stream_poll_interval}
            />
          )}

          {/* 保留地点详情模态框 */}
          {world && selectedLocation && (
            <LocationDetailModal
              isOpen={isLocationExpanded}
              onClose={() => setIsLocationExpanded(false)}
              world={world}
              locationId={selectedLocation.id}
              onLocationChange={(locId) => setHighlightedLocationId(locId)}
              runId={runId}
            />
          )}
        </div>

        {/* 第三列：故事时间线 */}
        <div className="flex h-full min-h-0 flex-col">
          <StoryTimeline
            chapters={storyChapters}
            onExpand={() => setIsTimelineExpanded(true)}
          />
        </div>

        {/* 事件回放弹窗 */}
        <TimelineModal
          isOpen={isTimelineExpanded}
          onClose={() => setIsTimelineExpanded(false)}
          runId={runId}
        />

        {/* 智能体详情弹窗 */}
        {selectedAgentId && (
          <AgentDetailModal
            isOpen={isAgentExpanded}
            onClose={() => setIsAgentExpanded(false)}
            runId={runId}
            agentId={selectedAgentId}
          />
        )}
      </div>
    </div>
  );
}
