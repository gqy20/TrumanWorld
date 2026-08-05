"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { AgentAvatar } from "@/components/agent-avatar";
import { TownMap } from "@/components/town-map";
import { VoxelWorldRenderer } from "@/components/voxel-world-renderer";
import type { VoxelCameraFocusRequest } from "@/components/voxel/camera-controller";
import { WorldViewToggle, type WorldView } from "@/components/world-view-toggle";
import { isWorldView } from "@/components/world-view-toggle";
import { GodotWorldHost } from "@/components/godot/godot-world-host";
import type { GodotSelectionPayload } from "@/components/godot/protocol";
import { toGodotWorldSnapshot } from "@/components/godot/world-snapshot-adapter";
import { inferAgentStatus } from "@/lib/agent-utils";
import { IntelligenceStreamModal } from "@/components/intelligence-stream-modal";
import { LocationDetailModal } from "@/components/location-detail-modal";
import { WorldHealthPanel } from "@/components/world-health-panel";
import { StoryTimeline } from "@/components/story-timeline";
import { TimelineModal } from "@/components/timeline-modal";
import { AgentDetailModal } from "@/components/agent-detail-modal";
import { ScrollArea } from "@/components/scroll-area";
import { useWorld } from "@/components/world-context";
import {
  calculateWorldHealthMetrics,
  aggregateStoryChapters,
} from "@/lib/world-insights";
import {
  beatBadge,
  buildWorldNameMaps,
  formatGoal,
  getWorldAgents,
  getLocationHeadlineEvents,
  locationBeat,
  locationTone,
} from "@/lib/world-utils";
import { useUiSearchParams } from "@/lib/ui-url-state";
import { describeWorldEvent } from "@/lib/event-utils";
import { buildSceneWorld } from "@/lib/world-scene-adapter";

type Props = {
  runId: string;
};

export function WorldCanvas({ runId }: Props) {
  const { world } = useWorld();
  const { searchParams, replaceSearchParams } = useUiSearchParams();
  const [highlightedLocationId, setHighlightedLocationId] = useState<string | null>(null);
  const [isInspectorOpen, setIsInspectorOpen] = useState(false);
  const [cameraFocusRequest, setCameraFocusRequest] =
    useState<VoxelCameraFocusRequest | null>(null);

  const modal = searchParams.get("modal");
  const selectedAgentId = searchParams.get("agent");
  const selectedLocationIdFromQuery = searchParams.get("loc");
  const requestedView = searchParams.get("view");
  const mapView: WorldView = isWorldView(requestedView) ? requestedView : "stage";
  const isStreamExpanded = modal === "stream";
  const isLocationExpanded = modal === "location";
  const isTimelineExpanded = modal === "timeline";
  const isAgentExpanded = modal === "agent" && Boolean(selectedAgentId);

  // 监听打开时间线弹窗的事件
  useEffect(() => {
    const handleOpenTimeline = () => replaceSearchParams({ modal: "timeline" });
    window.addEventListener("openTimelineModal", handleOpenTimeline);
    return () => window.removeEventListener("openTimelineModal", handleOpenTimeline);
  }, [replaceSearchParams]);

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
    const queryLocationId =
      selectedLocationIdFromQuery &&
      world.locations.some((location) => location.id === selectedLocationIdFromQuery)
        ? selectedLocationIdFromQuery
        : null;

    setHighlightedLocationId((current) => {
      if (queryLocationId) return queryLocationId;
      return current && world.locations.some((location) => location.id === current)
        ? current
        : world.locations[0].id;
    });
  }, [world, selectedLocationIdFromQuery]);

  useEffect(() => {
    if (!isInspectorOpen) return;
    const closeInspector = (event: KeyboardEvent) => {
      if (event.key === "Escape") setIsInspectorOpen(false);
    };
    window.addEventListener("keydown", closeInspector);
    return () => window.removeEventListener("keydown", closeInspector);
  }, [isInspectorOpen]);

  const { agentNameMap, locationNameMap } = useMemo(() => {
    if (!world) {
      return {
        agentNameMap: {} as Record<string, string>,
        locationNameMap: {} as Record<string, string>,
      };
    }

    const { agentNameMap, locationNameMap } = buildWorldNameMaps(world);
    return {
      agentNameMap,
      locationNameMap,
    };
  }, [world]);
  const worldAgents = useMemo(
    () => (world ? getWorldAgents(world) : []),
    [world],
  );
  const sceneWorld = useMemo(() => (world ? buildSceneWorld(world) : null), [world]);
  const godotSnapshot = useMemo(
    () => (world ? toGodotWorldSnapshot(world) : null),
    [world],
  );
  const godotFocusEntity = useMemo<GodotSelectionPayload | null>(() => {
    if (selectedAgentId) return { kind: "agent", id: selectedAgentId };
    if (selectedLocationIdFromQuery) {
      return { kind: "location", id: selectedLocationIdFromQuery };
    }
    return null;
  }, [selectedAgentId, selectedLocationIdFromQuery]);

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
  const selectedLocationHeadlineEvents = selectedLocation
    ? getLocationHeadlineEvents(selectedLocation.id, world.recent_events, 2)
    : [];
  const requestCameraFocus = (kind: VoxelCameraFocusRequest["kind"], id: string) => {
    setCameraFocusRequest((current) => ({ kind, id, revision: (current?.revision ?? 0) + 1 }));
  };
  const selectWorldView = (view: WorldView) => replaceSearchParams({ view });
  const handleGodotSelection = (selection: GodotSelectionPayload) => {
    if (selection.kind === "location") {
      setHighlightedLocationId(selection.id);
      setIsInspectorOpen(true);
      replaceSearchParams({ loc: selection.id, modal: null });
      return;
    }
    if (selection.kind === "agent") {
      const targetLocationId = world.locations.find((location) =>
        location.occupants.some((agent) => agent.id === selection.id),
      )?.id;
      if (targetLocationId) setHighlightedLocationId(targetLocationId);
      replaceSearchParams({ modal: "agent", agent: selection.id });
    }
  };

  return (
    <div className="flex min-h-0 flex-col gap-4 xl:h-full">
      <div
        data-testid="world-stage-layout"
        className="relative grid min-h-0 min-w-0 grid-cols-1 xl:h-full"
      >
        <div className="min-w-0 sm:min-h-[620px] xl:h-full">
          <div className="flex h-full min-h-0 min-w-0 flex-col sm:min-h-[460px]">
            <div className="relative min-h-0 min-w-0 flex-1">
              <div className="pointer-events-none absolute top-3 left-3 z-20 flex max-w-[calc(100%-1.5rem)] items-center gap-2 lg:left-12">
                <div className="pointer-events-auto">
                  <WorldViewToggle currentView={mapView} onToggle={selectWorldView} />
                </div>
                <button
                  type="button"
                  aria-expanded={isInspectorOpen}
                  aria-controls="world-inspector"
                  aria-label={isInspectorOpen ? "收起世界信息" : "打开世界信息"}
                  title={isInspectorOpen ? "关闭世界信息（Esc）" : "打开世界信息"}
                  onClick={() => setIsInspectorOpen((current) => !current)}
                  className="pointer-events-auto inline-flex h-9 items-center gap-2 rounded-xl bg-[#f7f7f3]/95 px-3 text-xs font-medium text-slate-600 shadow-[0_2px_8px_rgba(15,23,42,0.12)] transition-colors duration-200 hover:bg-white hover:text-slate-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-900"
                >
                  <PanelOpenIcon />
                  <span>{isInspectorOpen ? "收起信息" : "世界信息"}</span>
                </button>
              </div>
              {mapView === "stage" && sceneWorld ? (
                <VoxelWorldRenderer
                  sceneWorld={sceneWorld}
                  highlightedLocationId={highlightedLocationId}
                  highlightedAgentId={selectedAgentId}
                  cameraFocusRequest={cameraFocusRequest}
                  onLocationClick={(locationId) => {
                    setHighlightedLocationId(locationId);
                    setIsInspectorOpen(true);
                    requestCameraFocus("location", locationId);
                    replaceSearchParams({ loc: locationId, modal: null });
                  }}
                  onAgentClick={(agentId) => {
                    const targetLocationId =
                      world.locations.find((location) =>
                        location.occupants.some((agent) => agent.id === agentId),
                      )?.id ?? null;
                    if (targetLocationId) {
                      setHighlightedLocationId(targetLocationId);
                    }
                    requestCameraFocus("agent", agentId);
                    replaceSearchParams({ modal: "agent", agent: agentId });
                  }}
                />
              ) : mapView === "director" ? (
                <TownMap
                  world={world}
                  agentNameMap={agentNameMap}
                  hasStageControls
                  highlightedLocationId={highlightedLocationId}
                  onLocationClick={(locationId) => {
                    setHighlightedLocationId(locationId);
                    setIsInspectorOpen(true);
                    replaceSearchParams({ loc: locationId, modal: null });
                  }}
                  onAgentClick={(agentId) => {
                    replaceSearchParams({ modal: "agent", agent: agentId });
                  }}
                />
              ) : godotSnapshot ? (
                <GodotWorldHost
                  embedded
                  runId={runId}
                  snapshot={godotSnapshot}
                  focusEntity={godotFocusEntity}
                  onSelectionChange={handleGodotSelection}
                />
              ) : (
                <div
                  role="status"
                  className="flex h-full min-h-[540px] items-center justify-center bg-[#0e141d] px-6 text-center text-sm text-slate-300"
                >
                  当前场景尚未导出兼容的 3D 地图，请先完成 Godot 地图构建。
                </div>
              )}
            </div>
          </div>
        </div>

        {/* 右侧：世界状态、地点详情、故事线 */}
        <ScrollArea
          as="aside"
          id="world-inspector"
          data-testid="world-inspector"
          aria-label="世界信息"
          aria-hidden={!isInspectorOpen}
          className={`absolute inset-y-3 right-3 z-30 w-[min(340px,calc(100%-1.5rem))] overflow-y-auto overflow-x-hidden rounded-2xl border border-[#d8d8d0] bg-[#f7f7f3] p-4 shadow-[0_12px_36px_rgba(23,32,51,0.18)] ${isInspectorOpen ? "flex flex-col gap-5" : "hidden"}`}
        >
          <div className="flex items-center justify-between border-b border-slate-200 pb-3">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400">Director view</p>
              <h2 className="mt-1 text-sm font-semibold text-ink">世界信息</h2>
            </div>
            <button
              type="button"
              onClick={() => setIsInspectorOpen(false)}
              aria-label="关闭世界信息"
              className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-500 transition-colors duration-200 hover:border-slate-300 hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
            >
              <CloseIcon />
            </button>
          </div>
          {/* 世界健康度面板 */}
          {healthMetrics && <WorldHealthPanel metrics={healthMetrics} runId={runId} world={world} />}

          {/* 地点详情卡片 */}
          <div className="rounded-[28px] border border-slate-200 bg-white/80 p-4 shadow-xs">
            <div className="flex items-center justify-between gap-3">
              <div className="flex min-w-0 items-center gap-2">
                <h2 className="min-w-0 text-[15px] font-semibold tracking-[-0.01em] text-ink">
                  {selectedLocation?.name ?? "暂无地点"}
                </h2>
                {selectedLocation && (
                  <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-medium ${locationTone(selectedLocation.location_type)}`}>
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
                  onClick={() =>
                    replaceSearchParams({
                      modal: "location",
                      loc: selectedLocation?.id ?? null,
                    })
                  }
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
                {selectedLocationHeadlineEvents.length > 0 ? (
                  <div className="rounded-2xl border border-slate-100 bg-slate-50/80 p-3">
                    <p className="text-[10px] font-medium uppercase tracking-[0.18em] text-slate-400">
                      刚刚发生
                    </p>
                    <div className="mt-2 space-y-1.5">
                      {selectedLocationHeadlineEvents.map((event) => (
                        <div key={event.id} className="flex items-start gap-2 text-[13px] text-slate-600">
                          <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-moss/50" />
                          <span className="line-clamp-2">
                            {describeWorldEvent(event, agentNameMap, locationNameMap)}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}
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
                          <p className="truncate text-[13px] font-medium text-ink group-hover:text-moss">{agent.name}</p>
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

          <StoryTimeline
            chapters={storyChapters}
            onExpand={() => replaceSearchParams({ modal: "timeline" })}
          />

        </ScrollArea>

        <IntelligenceStreamModal
          isOpen={isStreamExpanded}
          onClose={() => replaceSearchParams({ modal: null })}
          world={world}
          runId={runId}
          maxEvents={world.health_metrics_config?.ui_intelligence_stream_max_events}
          pollIntervalMs={world.health_metrics_config?.ui_intelligence_stream_poll_interval}
        />

        {selectedLocation && (
          <LocationDetailModal
            isOpen={isLocationExpanded}
            onClose={() => replaceSearchParams({ modal: null })}
            world={world}
            locationId={selectedLocation.id}
            onLocationChange={(locId) => {
              setHighlightedLocationId(locId);
              replaceSearchParams({ modal: "location", loc: locId });
            }}
            runId={runId}
          />
        )}

        {/* 事件回放弹窗 */}
        <TimelineModal
          isOpen={isTimelineExpanded}
          onClose={() => replaceSearchParams({ modal: null })}
          runId={runId}
          agents={worldAgents}
        />

        {/* 智能体详情弹窗 */}
        {selectedAgentId && (
          <AgentDetailModal
            isOpen={isAgentExpanded}
            onClose={() => replaceSearchParams({ modal: null, agent: null })}
            runId={runId}
            agentId={selectedAgentId}
          />
        )}
      </div>
    </div>
  );
}

function CloseIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 20 20" fill="none" className="h-4 w-4">
      <path
        d="m6 6 8 8m0-8-8 8"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function PanelOpenIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 20 20" fill="none" className="h-4 w-4">
      <rect x="2.75" y="3.25" width="14.5" height="13.5" rx="2" stroke="currentColor" strokeWidth="1.5" />
      <path d="M12.5 3.5v13" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}
