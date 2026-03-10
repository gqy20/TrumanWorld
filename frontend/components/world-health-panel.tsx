"use client";

import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { motion, AnimatePresence } from "framer-motion";
import type { WorldHealthMetrics, Trend } from "@/lib/world-insights";
import type { DirectorMemory } from "@/lib/types";
import {
  getTrendIcon,
  getTrendColor,
  getScoreColor,
  getScoreBgColor,
} from "@/lib/world-insights";
import { DirectorEventForm } from "@/components/director-event-form";
import { useWorld } from "@/components/world-context";
import { getDirectorMemoriesResult } from "@/lib/api";
import type { WorldSnapshot } from "@/lib/types";
import { LoadingState } from "@/components/loading-state";
import { ErrorState } from "@/components/error-state";
import { Modal } from "@/components/modal";

interface WorldHealthPanelProps {
  metrics: WorldHealthMetrics;
  runId: string;
  world?: WorldSnapshot;
}

type ActivityType = "working" | "socializing" | "resting" | "commuting";

interface ActivityModalState {
  isOpen: boolean;
  type: ActivityType | null;
  title: string;
  agents: { id: string; name: string; location?: string }[];
}

export function WorldHealthPanel({ metrics, runId, world }: WorldHealthPanelProps) {
  const [isDirectorExpanded, setIsDirectorExpanded] = useState(false);
  const [activityModal, setActivityModal] = useState<ActivityModalState>({
    isOpen: false,
    type: null,
    title: "",
    agents: [],
  });
  const { refresh } = useWorld();

  // 根据活动类型获取智能体列表
  const getAgentsByActivity = (type: ActivityType): { id: string; name: string; location?: string }[] => {
    if (!world) return [];
    const agents: { id: string; name: string; location?: string }[] = [];
    const locationTypeMap = new Map(world.locations.map((l) => [l.id, l.location_type]));

    for (const location of world.locations) {
      for (const agent of location.occupants) {
        const goal = agent.current_goal?.toLowerCase() ?? "";
        const locationType = agent.current_location_id
          ? locationTypeMap.get(agent.current_location_id)
          : undefined;
        const isWorkContext = locationType != null && locationType !== "home" && locationType !== "plaza";

        let match = false;
        switch (type) {
          case "working":
            match = goal === "work" && isWorkContext;
            break;
          case "socializing":
            match = goal === "talk";
            break;
          case "resting":
            match = goal === "rest" || goal === "wander" ||
                    (goal !== "work" && goal !== "talk" && goal !== "commute" &&
                     goal !== "go_home" && !goal.startsWith("move:"));
            break;
          case "commuting":
            match = goal === "commute" || goal === "go_home" || goal.startsWith("move:") ||
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
    const agents = getAgentsByActivity(type);
    setActivityModal({ isOpen: true, type, title, agents });
  };
  return (
    <div className="rounded-[28px] border border-white/70 bg-white/80 p-4 shadow-xs backdrop-blur-sm">
      {/* 标题区 */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-ink">🌍 世界健康度</h2>
        <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-100 bg-emerald-50 px-2 py-0.5 text-[11px] text-emerald-600">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" />
          实时
        </span>
      </div>

      {/* 核心指标区 - 紧凑排列 */}
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
          suggestion={
            metrics.socialActivity < 30
              ? "居民互动较少，建议增加对话"
              : undefined
          }
          description="居民之间的交流频率"
        />
        <MetricBar
          label="Truman怀疑度"
          value={metrics.trumanSuspicion}
          trend={metrics.suspicionTrend}
          description="Truman 对世界的信任程度"
        />
      </div>

      {/* 导演干预 - 独立卡片区域 */}
      <div className="mt-4">
        <DirectorStats
          stats={metrics.directorStats}
          onClick={() => setIsDirectorExpanded(true)}
        />
        <DirectorInterventionModal
          isOpen={isDirectorExpanded}
          onClose={() => setIsDirectorExpanded(false)}
          stats={metrics.directorStats}
          runId={runId}
          onInjected={refresh}
          maxMemories={world?.health_metrics_config?.ui_director_panel_max_memories}
        />
      </div>

      {/* 活动分布 - 与下方统计合并视觉区域 */}
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
        {/* 今日统计 - 内嵌在活动区域底部 */}
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

      {/* 活动分布详情弹窗 */}
      <ActivityDetailModal
        isOpen={activityModal.isOpen}
        onClose={() => setActivityModal((prev) => ({ ...prev, isOpen: false }))}
        title={activityModal.title}
        agents={activityModal.agents}
      />
    </div>
  );
}

// ============================================================================
// 活动详情弹窗
// ============================================================================

interface ActivityDetailModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  agents: { id: string; name: string; location?: string }[];
}

function ActivityDetailModal({ isOpen, onClose, title, agents }: ActivityDetailModalProps) {
  return (
    <Modal isOpen={isOpen} onClose={onClose} size="md" showCloseButton={false} title={title}>
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
                {agent.location && (
                  <span className="text-xs text-slate-400">📍 {agent.location}</span>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </Modal>
  );
}

// ============================================================================
// 指标条组件
// ============================================================================

interface MetricBarProps {
  label: string;
  value: number;
  trend: Trend;
  warning?: string;
  suggestion?: string;
  description?: string;
}

function MetricBar({
  label,
  value,
  trend,
  warning,
  suggestion,
  description,
}: MetricBarProps) {
  const scoreColor = getScoreColor(value);
  const scoreBgColor = getScoreBgColor(value);
  const trendIcon = getTrendIcon(trend);
  const trendColor = getTrendColor(trend);

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-slate-700">{label}</span>
          {description && (
            <Tooltip text={description} />
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className={`text-sm font-semibold ${scoreColor}`}>
            {value}%
          </span>
          <span className={`text-xs ${trendColor}`}>{trendIcon}</span>
        </div>
      </div>

      {/* 进度条 */}
      <div className="h-2 overflow-hidden rounded-full bg-slate-100">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${value}%` }}
          transition={{ duration: 0.5, ease: "easeOut" }}
          className={`h-full rounded-full ${scoreBgColor}`}
        />
      </div>

      {/* 警告或建议 */}
      {warning && (
        <div className="flex items-start gap-1.5 text-xs text-amber-600">
          <span>⚠️</span>
          <span>{warning}</span>
        </div>
      )}
      {suggestion && !warning && (
        <div className="flex items-start gap-1.5 text-xs text-blue-600">
          <span>💡</span>
          <span>{suggestion}</span>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// 导演统计组件
// ============================================================================

interface DirectorStatsProps {
  stats: {
    total: number;
    executed: number;
    executionRate: number;
  };
  onClick?: () => void;
}

function DirectorStats({ stats, onClick }: DirectorStatsProps) {
  const hasIssue = stats.executionRate < 50 && stats.total > 0;
  const queuedCount = stats.total - stats.executed;

  return (
    <button
      type="button"
      onClick={onClick}
      className="w-full rounded-xl bg-slate-50 p-3 text-left transition hover:bg-slate-100"
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-slate-700">🎬 导演干预</span>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`text-xs font-medium ${
              hasIssue ? "text-amber-600" : "text-slate-500"
            }`}
          >
            {stats.executionRate}% 消费率
          </span>
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            className="h-4 w-4 text-slate-400"
          >
            <path d="M9 5l7 7-7 7" />
          </svg>
        </div>
      </div>

      <div className="mt-2 flex items-center gap-4">
        <div className="flex items-center gap-1.5">
          <span className="text-lg font-semibold text-slate-800">
            {stats.total}
          </span>
          <span className="text-xs text-slate-500">计划</span>
        </div>
        <div className="h-4 w-px bg-slate-200" />
        <div className="flex items-center gap-1.5">
          <span className="text-lg font-semibold text-emerald-600">
            {stats.executed}
          </span>
          <span className="text-xs text-slate-500">已消费</span>
        </div>
        <div className="h-4 w-px bg-slate-200" />
        <div className="flex items-center gap-1.5">
          <span
            className={`text-lg font-semibold ${
              hasIssue ? "text-amber-600" : "text-slate-600"
            }`}
          >
            {queuedCount}
          </span>
          <span className="text-xs text-slate-500">排队中</span>
        </div>
      </div>

      {hasIssue && (
        <div className="mt-2 flex items-start gap-1.5 text-xs text-amber-600">
          <span>⚠️</span>
          <span>干预消费率较低，建议检查 tick 推进和干预传递流程</span>
        </div>
      )}
    </button>
  );
}

// ============================================================================
// 活动徽章组件
// ============================================================================

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
      className={`flex flex-col items-center rounded-lg border px-2 py-2 transition-colors ${colorClasses[color]} ${onClick ? "cursor-pointer" : ""}`}
    >
      <span className="text-base">{icon}</span>
      <span className="text-sm font-semibold">{count}</span>
      <span className="text-[10px] text-slate-500">{label}</span>
    </Component>
  );
}

// ============================================================================
// 统计项组件
// ============================================================================

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
        highlight
          ? "bg-amber-50 border border-amber-100"
          : "bg-slate-100/50"
      }`}
    >
      <span className="text-sm">{icon}</span>
      <span
        className={`text-sm font-semibold ${
          highlight ? "text-amber-700" : "text-slate-700"
        }`}
      >
        {value}
      </span>
      <span className="text-[10px] text-slate-500">{label}</span>
    </div>
  );
}

// ============================================================================
// 导演干预详情弹窗
// ============================================================================

interface DirectorInterventionModalProps {
  isOpen: boolean;
  onClose: () => void;
  stats: {
    total: number;
    executed: number;
    executionRate: number;
  };
  runId: string;
  onInjected: () => void;
  maxMemories?: number;
}

type DirectorFilter = "all" | "queued" | "consumed" | "expired";

function DirectorInterventionModal({
  isOpen,
  onClose,
  stats,
  runId,
  onInjected,
  maxMemories,
}: DirectorInterventionModalProps) {
  const [selectedFilter, setSelectedFilter] = useState<DirectorFilter>("all");
  const [memories, setMemories] = useState<DirectorMemory[]>([]);
  const [isLoadingMemories, setIsLoadingMemories] = useState(false);
  const [memoryError, setMemoryError] = useState<string | null>(null);
  const queuedCount = memories.filter((memory) => memory.delivery_status === "queued").length;
  const consumedCount = memories.filter((memory) => memory.delivery_status === "consumed").length;
  const expiredCount = memories.filter((memory) => memory.delivery_status === "expired").length;
  const hasIssue = stats.executionRate < 50 && stats.total > 0;

  useEffect(() => {
    if (!isOpen) return;

    let cancelled = false;

    async function loadMemories() {
      setIsLoadingMemories(true);
      setMemoryError(null);
      const result = await getDirectorMemoriesResult(runId, maxMemories ?? 100);
      if (cancelled) return;
      if (result.data) {
        setMemories(result.data.memories);
      } else {
        setMemories([]);
        setMemoryError(result.error === "network_error" ? "后端不可达" : "明细加载失败");
      }
      setIsLoadingMemories(false);
    }

    void loadMemories();

    return () => {
      cancelled = true;
    };
  }, [isOpen, runId, maxMemories]);

  const filteredMemories = useMemo(() => {
    if (selectedFilter === "queued") {
      return memories.filter((memory) => memory.delivery_status === "queued");
    }
    if (selectedFilter === "consumed") {
      return memories.filter((memory) => memory.delivery_status === "consumed");
    }
    if (selectedFilter === "expired") {
      return memories.filter((memory) => memory.delivery_status === "expired");
    }
    return memories;
  }, [memories, selectedFilter]);

  const handleInjected = () => {
    onInjected();
    void (async () => {
      const result = await getDirectorMemoriesResult(runId, maxMemories ?? 100);
      if (result.data) {
        setMemories(result.data.memories);
      }
    })();
  };

  const modal = (
    <AnimatePresence>
      {isOpen && (
        <Modal
          isOpen={isOpen}
          onClose={onClose}
          size="xl"
          showCloseButton={false}
          title="导演干预控制台"
          subtitle="管理和监控所有导演干预计划"
        >

            {/* 主体：左右两列 */}
            <div className="flex min-h-0 flex-1 overflow-hidden">
              {/* 左侧：导演干预 + 导航 + 执行率 */}
              <div className="flex w-72 shrink-0 flex-col border-r border-slate-100 bg-slate-50/50">
                {/* 导演干预表单 */}
                <div className="border-b border-slate-100 p-4">
                  <h3 className="mb-3 text-sm font-semibold text-slate-700">🎬 导演干预</h3>
                  <DirectorEventForm runId={runId} onInjected={handleInjected} compact />
                </div>

                {/* 导航菜单 */}
                <div className="flex-1 overflow-auto p-4">
                  <div className="mb-2 text-xs font-medium text-slate-400 uppercase tracking-wider">
                    干预明细
                  </div>
                  <div className="space-y-1">
                    <NavItem
                      icon="📋"
                      label="全部"
                      count={memories.length}
                      active={selectedFilter === "all"}
                      onClick={() => setSelectedFilter("all")}
                    />
                    <NavItem
                      icon="✅"
                      label="已消费"
                      count={consumedCount}
                      active={selectedFilter === "consumed"}
                      onClick={() => setSelectedFilter("consumed")}
                      tone="emerald"
                    />
                    <NavItem
                      icon="⏳"
                      label="排队中"
                      count={queuedCount}
                      active={selectedFilter === "queued"}
                      onClick={() => setSelectedFilter("queued")}
                      tone={hasIssue ? "amber" : "slate"}
                    />
                    <NavItem
                      icon="⌛"
                      label="已过期"
                      count={expiredCount}
                      active={selectedFilter === "expired"}
                      onClick={() => setSelectedFilter("expired")}
                      tone="slate"
                    />
                  </div>
                </div>

                {/* 执行率 */}
                <div className="border-t border-slate-100 p-4">
                  <div className="rounded-2xl bg-white p-4 shadow-xs">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-slate-500">执行率</span>
                      <span className={`font-bold ${hasIssue ? "text-amber-600" : "text-emerald-600"}`}>
                        {stats.executionRate}%
                      </span>
                    </div>
                    <div className="mt-2.5 h-2 overflow-hidden rounded-full bg-slate-100">
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${stats.executionRate}%` }}
                        transition={{ duration: 0.5 }}
                        className={`h-full rounded-full ${hasIssue ? "bg-amber-500" : "bg-emerald-500"}`}
                      />
                    </div>
                    {hasIssue && (
                      <p className="mt-2.5 text-xs text-amber-600">⚠️ 执行率较低</p>
                    )}
                  </div>
                </div>
              </div>

              {/* 右侧：明细列表 */}
              <div className="flex-1 overflow-auto px-6 py-5">
                <div className="mb-4 flex items-center gap-2">
                  <span className="text-lg font-semibold text-ink">
                    {selectedFilter === "all" && "全部干预"}
                    {selectedFilter === "consumed" && "已消费"}
                    {selectedFilter === "queued" && "排队中"}
                    {selectedFilter === "expired" && "已过期"}
                  </span>
                  <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-sm font-medium text-slate-600">
                    {filteredMemories.length}
                  </span>
                </div>

                <div className="space-y-3">
                  {isLoadingMemories ? (
                    <LoadingState message="正在加载导演明细..." size="sm" />
                  ) : memoryError ? (
                    <ErrorState
                      message={memoryError}
                      onRetry={() => {
                        void (async () => {
                          setIsLoadingMemories(true);
                          setMemoryError(null);
                          const result = await getDirectorMemoriesResult(runId, maxMemories ?? 100);
                          if (result.data) {
                            setMemories(result.data.memories);
                          } else {
                            setMemoryError(result.error === "network_error" ? "后端不可达" : "明细加载失败");
                          }
                          setIsLoadingMemories(false);
                        })();
                      }}
                      size="sm"
                    />
                  ) : filteredMemories.length === 0 ? (
                    <div className="rounded-2xl border border-slate-100 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">
                      暂无{selectedFilter === "all" ? "" : "此类"}干预记录
                    </div>
                  ) : (
                    filteredMemories.map((memory) => (
                      <DirectorMemoryCard key={memory.id} memory={memory} />
                    ))
                  )}
                </div>
              </div>
            </div>
        </Modal>
      )}
    </AnimatePresence>
  );

  if (typeof document === "undefined") return null;
  return createPortal(modal, document.body);
}

function NavItem({
  icon,
  label,
  count,
  active,
  onClick,
  tone = "slate",
}: {
  icon: string;
  label: string;
  count: number;
  active: boolean;
  onClick: () => void;
  tone?: "slate" | "emerald" | "amber";
}) {
  const toneClasses = {
    slate: {
      active: "bg-slate-100 text-slate-900",
      inactive: "text-slate-600 hover:bg-slate-50 hover:text-slate-900",
    },
    emerald: {
      active: "bg-emerald-50 text-emerald-700",
      inactive: "text-slate-600 hover:bg-emerald-50/50 hover:text-emerald-700",
    },
    amber: {
      active: "bg-amber-50 text-amber-700",
      inactive: "text-slate-600 hover:bg-amber-50/50 hover:text-amber-700",
    },
  };

  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex w-full items-center justify-between rounded-xl px-3 py-2.5 text-sm transition ${
        active ? toneClasses[tone].active : toneClasses[tone].inactive
      }`}
    >
      <div className="flex items-center gap-2.5">
        <span className="text-base">{icon}</span>
        <span className="font-medium">{label}</span>
      </div>
      <span className={`rounded-md px-2 py-0.5 text-xs font-semibold ${
        active
          ? tone === "emerald"
            ? "bg-emerald-100 text-emerald-800"
            : tone === "amber"
              ? "bg-amber-100 text-amber-800"
              : "bg-white text-slate-700 shadow-xs"
          : "bg-slate-100 text-slate-600"
      }`}>
        {count}
      </span>
    </button>
  );
}

function DirectorMemoryCard({ memory }: { memory: DirectorMemory }) {
  const statusMeta =
    memory.delivery_status === "consumed"
      ? {
          label: "已消费",
          tone: "bg-emerald-50 text-emerald-700 border-emerald-100",
        }
      : memory.delivery_status === "expired"
        ? {
            label: "已过期",
            tone: "bg-slate-100 text-slate-700 border-slate-200",
          }
        : {
            label: "排队中",
            tone: "bg-amber-50 text-amber-700 border-amber-100",
          };

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-xs">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className={`rounded-full border px-2.5 py-1 text-xs font-medium ${statusMeta.tone}`}>
            {statusMeta.label}
          </span>
          <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600">
            Tick {memory.tick_no}
          </span>
          <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600">
            {memory.scene_goal}
          </span>
        </div>
        <span className="text-xs text-slate-400">
          {new Date(memory.created_at).toLocaleString()}
        </span>
      </div>

      <div className="mt-3 space-y-2 text-sm text-slate-600">
        <p><span className="font-medium text-slate-700">状态：</span>{statusMeta.label}</p>
        {memory.message_hint ? <p><span className="font-medium text-slate-700">内容：</span>{memory.message_hint}</p> : null}
        {memory.reason ? <p><span className="font-medium text-slate-700">原因：</span>{memory.reason}</p> : null}
        {memory.location_name || memory.location_hint ? (
          <p><span className="font-medium text-slate-700">地点：</span>{memory.location_name ?? memory.location_hint}</p>
        ) : null}
        {memory.target_agent_name || memory.target_agent_id ? (
          <p><span className="font-medium text-slate-700">目标：</span>{memory.target_agent_name ?? memory.target_agent_id}</p>
        ) : null}
        {memory.target_cast_names.length > 0 ? (
          <p><span className="font-medium text-slate-700">执行演员：</span>{memory.target_cast_names.join("、")}</p>
        ) : null}
      </div>
    </div>
  );
}

// ============================================================================
// Tooltip 组件
// ============================================================================

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
