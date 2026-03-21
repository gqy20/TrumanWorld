"use client";

import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import useSWR from "swr";

import { DirectorInterventionModal, DirectorStats } from "@/components/world-health-director";
import { SystemStatusModal, SystemStatusPanel } from "@/components/world-health-system";
import { Modal } from "@/components/modal";
import { useUiSearchParams } from "@/lib/ui-url-state";
import { useWorld } from "@/components/world-context";
import { getScoreBgColor, getScoreColor, getTrendColor, getTrendIcon } from "@/lib/world-insights";
import type { Trend, WorldHealthMetrics } from "@/lib/world-insights";
import { getSystemMetrics, getSystemOverview } from "@/lib/api";
import type { SystemMetrics, SystemOverview, WorldSnapshot } from "@/lib/types";
import { isAgentSociallyEngaged } from "@/lib/world-utils";

interface WorldHealthPanelProps {
  metrics: WorldHealthMetrics;
  runId: string;
  world?: WorldSnapshot;
}

type ActivityType = "working" | "socializing" | "resting" | "commuting";

interface ActivityModalState {
  isOpen: boolean;
  title: string;
  agents: { id: string; name: string; location?: string }[];
}

export function WorldHealthPanel({ metrics, runId, world }: WorldHealthPanelProps) {
  const { searchParams, replaceSearchParams } = useUiSearchParams();
  const [activityModal, setActivityModal] = useState<ActivityModalState>({
    isOpen: false,
    title: "",
    agents: [],
  });
  const modal = searchParams.get("modal");
  const isDirectorExpanded = modal === "director";
  const isSystemExpanded = modal === "system";
  const systemRefreshInterval = world?.run.status === "running" ? 5000 : 0;
  const { refresh } = useWorld();
  const { data: systemMetrics } = useSWR<SystemMetrics | null>("/metrics", getSystemMetrics, {
    refreshInterval: systemRefreshInterval,
    revalidateOnFocus: false,
    revalidateIfStale: isSystemExpanded || systemRefreshInterval > 0,
  });
  const { data: systemOverview } = useSWR<SystemOverview | null>(
    "/system/overview",
    getSystemOverview,
    {
      refreshInterval: systemRefreshInterval,
      revalidateOnFocus: false,
      revalidateIfStale: isSystemExpanded || systemRefreshInterval > 0,
    }
  );
  const agentNameMap = useMemo(
    () =>
      world
        ? Object.fromEntries(
            world.locations.flatMap((loc) => loc.occupants).map((agent) => [agent.id, agent.name])
          )
        : {},
    [world]
  );

  const getAgentsByActivity = (
    type: ActivityType
  ): { id: string; name: string; location?: string }[] => {
    if (!world) return [];
    const agents: { id: string; name: string; location?: string }[] = [];
    const locationTypeMap = new Map(world.locations.map((location) => [location.id, location.location_type]));

    for (const location of world.locations) {
      for (const agent of location.occupants) {
        const goal = agent.current_goal?.toLowerCase() ?? "";
        const locationType = agent.current_location_id
          ? locationTypeMap.get(agent.current_location_id)
          : undefined;
        const isWorkContext =
          locationType != null && locationType !== "home" && locationType !== "plaza";

        let match = false;
        switch (type) {
          case "working":
            match = goal === "work" && isWorkContext;
            break;
          case "socializing":
            match = isAgentSociallyEngaged(
              agent.id,
              agent.current_goal,
              world.recent_events,
              world.run.current_tick
            );
            break;
          case "resting":
            match =
              goal === "rest" ||
              goal === "wander" ||
              (goal !== "work" &&
                !isAgentSociallyEngaged(
                  agent.id,
                  agent.current_goal,
                  world.recent_events,
                  world.run.current_tick
                ) &&
                goal !== "commute" &&
                goal !== "go_home" &&
                !goal.startsWith("move:"));
            break;
          case "commuting":
            match =
              goal === "commute" ||
              goal === "go_home" ||
              goal.startsWith("move:") ||
              (goal === "work" && !isWorkContext);
            break;
        }

        if (match) {
          agents.push({ id: agent.id, name: agent.name, location: location.name });
        }
      }
    }

    return agents;
  };

  const handleActivityClick = (type: ActivityType, title: string) => {
    setActivityModal({ isOpen: true, title, agents: getAgentsByActivity(type) });
  };

  return (
    <div className="rounded-[28px] border border-white/70 bg-white/80 p-4 shadow-xs backdrop-blur-sm">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-ink">🌍 世界健康度</h2>
        <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-100 bg-emerald-50 px-2 py-0.5 text-[11px] text-emerald-600">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" />
          实时
        </span>
      </div>

      <div className="mt-4 space-y-3">
        <MetricBar
          label="剧情连贯性"
          value={metrics.continuityScore}
          trend={metrics.continuityTrend}
          warning={metrics.continuityIssue}
          description="世界运行的流畅程度"
        />
        <MetricBar
          label="社交活跃度"
          value={metrics.socialActivity}
          trend={metrics.socialTrend}
          suggestion={metrics.socialActivity < 30 ? "居民互动较少，建议增加对话" : undefined}
          description="居民之间的交流频率"
        />
        <MetricBar
          label="主体告警"
          value={metrics.subjectAlert}
          trend={metrics.subjectAlertTrend}
          description="当前场景主体角色的警觉/异常水平"
        />
      </div>

      <div className="mt-4">
        <SystemStatusPanel
          overview={systemOverview}
          metrics={systemMetrics}
          llmModel={world?.daily_stats?.llm_model}
          onClick={() => replaceSearchParams({ modal: "system" })}
        />
        <SystemStatusModal
          isOpen={isSystemExpanded}
          onClose={() => replaceSearchParams({ modal: null })}
          overview={systemOverview}
          metrics={systemMetrics}
          llmModel={world?.daily_stats?.llm_model}
        />
      </div>

      <div className="mt-4">
        <DirectorStats
          stats={metrics.directorStats}
          onClick={() => replaceSearchParams({ modal: "director" })}
        />
        <DirectorInterventionModal
          isOpen={isDirectorExpanded}
          onClose={() => replaceSearchParams({ modal: null })}
          stats={metrics.directorStats}
          runId={runId}
          onInjected={refresh}
          maxMemories={world?.health_metrics_config?.ui_director_panel_max_memories}
          locations={
            world?.locations.map((location) => ({
              id: location.id,
              name: location.name,
              location_type: location.location_type,
            })) ?? []
          }
          agentNameMap={agentNameMap}
        />
      </div>

      <div className="mt-4 rounded-xl border border-slate-100 bg-slate-50/50 p-3">
        <div className="text-xs font-medium text-slate-500">当前活动分布</div>
        <div className="mt-2 grid grid-cols-4 gap-2">
          <ActivityBadge
            icon="⚒️"
            label="在岗中"
            count={metrics.activitySummary.working}
            color="amber"
            onClick={() => handleActivityClick("working", "在岗中")}
          />
          <ActivityBadge
            icon="💬"
            label="对话中"
            count={metrics.activitySummary.socializing}
            color="emerald"
            onClick={() => handleActivityClick("socializing", "对话中")}
          />
          <ActivityBadge
            icon="😴"
            label="休息中"
            count={metrics.activitySummary.resting}
            color="slate"
            onClick={() => handleActivityClick("resting", "休息中")}
          />
          <ActivityBadge
            icon="🚶"
            label="通勤中"
            count={metrics.activitySummary.commuting}
            color="blue"
            onClick={() => handleActivityClick("commuting", "通勤中")}
          />
        </div>
        <div className="mt-3 grid grid-cols-3 gap-2 border-t border-slate-200/60 pt-3">
          <StatItem icon="💬" value={metrics.recentTalkCount} label="对话" />
          <StatItem icon="🚶" value={metrics.recentMoveCount} label="移动" />
          <StatItem
            icon="⚠️"
            value={metrics.recentRejectionCount}
            label="异常"
            highlight={metrics.recentRejectionCount > 0}
          />
        </div>
      </div>

      <ActivityDetailModal
        isOpen={activityModal.isOpen}
        onClose={() => setActivityModal((prev) => ({ ...prev, isOpen: false }))}
        title={activityModal.title}
        agents={activityModal.agents}
      />
    </div>
  );
}

interface ActivityDetailModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  agents: { id: string; name: string; location?: string }[];
}

function ActivityDetailModal({ isOpen, onClose, title, agents }: ActivityDetailModalProps) {
  return (
    <Modal isOpen={isOpen} onClose={onClose} variant="panel" showCloseButton={false} title={title}>
      <div className="max-h-[60vh] overflow-y-auto">
        {agents.length === 0 ? (
          <p className="py-8 text-center text-sm text-slate-400">暂无{title}的智能体</p>
        ) : (
          <div className="space-y-2">
            {agents.map((agent) => (
              <div
                key={agent.id}
                className="flex items-center justify-between rounded-xl border border-slate-100 bg-slate-50/50 p-3"
              >
                <span className="text-sm font-medium text-slate-700">{agent.name}</span>
                {agent.location && <span className="text-xs text-slate-400">📍 {agent.location}</span>}
              </div>
            ))}
          </div>
        )}
      </div>
    </Modal>
  );
}

interface MetricBarProps {
  label: string;
  value: number;
  trend: Trend;
  warning?: string;
  suggestion?: string;
  description?: string;
}

function MetricBar({ label, value, trend, warning, suggestion, description }: MetricBarProps) {
  const scoreColor = getScoreColor(value);
  const scoreBgColor = getScoreBgColor(value);
  const trendIcon = getTrendIcon(trend);
  const trendColor = getTrendColor(trend);

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-slate-700">{label}</span>
          {description ? <Tooltip text={description} /> : null}
        </div>
        <div className="flex items-center gap-2">
          <span className={`text-sm font-semibold ${scoreColor}`}>{value}%</span>
          <span className={`text-xs ${trendColor}`}>{trendIcon}</span>
        </div>
      </div>

      <div className="h-2 overflow-hidden rounded-full bg-slate-100">
        <motion.div
          initial={false}
          animate={{ width: `${value}%` }}
          transition={{ duration: 0.2, ease: "easeOut" }}
          className={`h-full rounded-full ${scoreBgColor}`}
        />
      </div>

      {warning ? (
        <div className="flex items-start gap-1.5 text-xs text-amber-600">
          <span>⚠️</span>
          <span>{warning}</span>
        </div>
      ) : suggestion ? (
        <div className="flex items-start gap-1.5 text-xs text-blue-600">
          <span>💡</span>
          <span>{suggestion}</span>
        </div>
      ) : null}
    </div>
  );
}

interface ActivityBadgeProps {
  icon: string;
  label: string;
  count: number;
  color: "amber" | "slate" | "blue" | "emerald";
  onClick?: () => void;
}

function ActivityBadge({ icon, label, count, color, onClick }: ActivityBadgeProps) {
  const colorClasses = {
    amber: "bg-amber-50 text-amber-700 border-amber-100 hover:bg-amber-100",
    slate: "bg-slate-50 text-slate-700 border-slate-100 hover:bg-slate-100",
    blue: "bg-blue-50 text-blue-700 border-blue-100 hover:bg-blue-100",
    emerald: "bg-emerald-50 text-emerald-700 border-emerald-100 hover:bg-emerald-100",
  };

  const Component = onClick ? "button" : "div";

  return (
    <Component
      onClick={onClick}
      className={`flex flex-col items-center rounded-lg border px-2 py-2 transition-colors ${colorClasses[color]} ${
        onClick ? "cursor-pointer" : ""
      }`}
    >
      <span className="text-base">{icon}</span>
      <span className="text-sm font-semibold">{count}</span>
      <span className="text-[10px] text-slate-500">{label}</span>
    </Component>
  );
}

interface StatItemProps {
  icon: string;
  value: number;
  label: string;
  highlight?: boolean;
}

function StatItem({ icon, value, label, highlight }: StatItemProps) {
  return (
    <div
      className={`flex flex-col items-center rounded-lg px-2 py-1.5 ${
        highlight ? "border border-amber-100 bg-amber-50" : "bg-slate-100/50"
      }`}
    >
      <span className="text-sm">{icon}</span>
      <span className={`text-sm font-semibold ${highlight ? "text-amber-700" : "text-slate-700"}`}>
        {value}
      </span>
      <span className="text-[10px] text-slate-500">{label}</span>
    </div>
  );
}

function Tooltip({ text }: { text: string }) {
  return (
    <div className="group relative">
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        className="h-3.5 w-3.5 cursor-help text-slate-400"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
        />
      </svg>
      <div className="absolute left-5 top-1/2 z-10 hidden -translate-y-1/2 whitespace-nowrap rounded-lg bg-slate-800 px-2 py-1 text-xs text-white shadow-lg group-hover:block">
        {text}
      </div>
    </div>
  );
}
