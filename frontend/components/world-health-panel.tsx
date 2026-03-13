"use client";

import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { motion, AnimatePresence } from "framer-motion";
import useSWR from "swr";
import type { WorldHealthMetrics, Trend } from "@/lib/world-insights";
import type { DirectorMemory, SystemMetrics, SystemOverview } from "@/lib/types";
import {
  getTrendIcon,
  getTrendColor,
  getScoreColor,
  getScoreBgColor,
} from "@/lib/world-insights";
import { DirectorEventForm } from "@/components/director-event-form";
import { useWorld } from "@/components/world-context";
import { getDirectorMemoriesResult, getSystemMetrics, getSystemOverview } from "@/lib/api";
import type { WorldSnapshot } from "@/lib/types";
import { LoadingState } from "@/components/loading-state";
import { ErrorState } from "@/components/error-state";
import { Modal, WorkspaceModalShell } from "@/components/modal";
import { useUiSearchParams } from "@/lib/ui-url-state";
import { isAgentSociallyEngaged } from "@/lib/world-utils";

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
  const { searchParams, replaceSearchParams } = useUiSearchParams();
  const [activityModal, setActivityModal] = useState<ActivityModalState>({
    isOpen: false,
    type: null,
    title: "",
    agents: [],
  });
  const modal = searchParams.get("modal");
  const isDirectorExpanded = modal === "director";
  const isSystemExpanded = modal === "system";
  const { refresh } = useWorld();
  const { data: systemMetrics } = useSWR<SystemMetrics | null>(
    "/metrics",
    getSystemMetrics,
    {
      refreshInterval: isSystemExpanded ? 5000 : 0,
      revalidateOnFocus: false,
      revalidateIfStale: isSystemExpanded,
    },
  );
  const { data: systemOverview } = useSWR<SystemOverview | null>(
    "/system/overview",
    getSystemOverview,
    {
      refreshInterval: isSystemExpanded ? 5000 : 0,
      revalidateOnFocus: false,
      revalidateIfStale: isSystemExpanded,
    },
  );

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
            match = isAgentSociallyEngaged(
              agent.id,
              agent.current_goal,
              world.recent_events,
              world.run.current_tick,
            );
            break;
          case "resting":
            match = goal === "rest" || goal === "wander" ||
                    (goal !== "work" &&
                     !isAgentSociallyEngaged(agent.id, agent.current_goal, world.recent_events, world.run.current_tick) &&
                     goal !== "commute" &&
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

      <div className="mt-4">
        <SystemStatusPanel
          overview={systemOverview}
          metrics={systemMetrics}
          onClick={() => replaceSearchParams({ modal: "system" })}
        />
        <SystemStatusModal
          isOpen={isSystemExpanded}
          onClose={() => replaceSearchParams({ modal: null })}
          overview={systemOverview}
          metrics={systemMetrics}
        />
      </div>

      {/* 导演干预 - 独立卡片区域 */}
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
          locations={world?.locations.map((location) => ({
            id: location.id,
            name: location.name,
            location_type: location.location_type,
          })) ?? []}
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

function formatBytes(bytes: number) {
  if (bytes <= 0) return "0 GB";
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

function formatComponentMemory(component: SystemOverview["components"]["backend"]) {
  if (component.uniqueBytes != null) {
    return formatBytes(component.uniqueBytes);
  }
  return formatBytes(component.rssBytes);
}

function getMemoryEstimateLabel(component: SystemOverview["components"]["backend"] | null | undefined) {
  return component?.uniqueBytes != null ? "内存估算" : "内存";
}

function formatCount(value: number) {
  return new Intl.NumberFormat("zh-CN").format(value);
}

const TOKEN_PRICE_CNY_PER_MILLION = {
  input: 2.1,
  output: 8.4,
  cacheRead: 0.21,
  cacheCreation: 2.625,
} as const;

function calculateTokenCostCny(tokens: number, unitPricePerMillion: number) {
  return (tokens / 1_000_000) * unitPricePerMillion;
}

function formatCnyCost(value: number) {
  return `¥${value.toFixed(4)}`;
}

function formatCpuPercent(value: number) {
  return `${value.toFixed(1)}%`;
}

function formatAge(timestamp: number) {
  const deltaSeconds = Math.max(0, Math.round((Date.now() - timestamp) / 1000));
  return `${deltaSeconds}s 前`;
}

function SystemStatusPanel({
  overview,
  metrics,
  onClick,
}: {
  overview: SystemOverview | null | undefined;
  metrics: SystemMetrics | null | undefined;
  onClick: () => void;
}) {
  const total = overview?.components.total;
  const memoryValue = total ? formatComponentMemory(total) : metrics ? formatBytes(metrics.processResidentMemoryBytes) : null;
  const cpuValue = total ? formatCpuPercent(total.cpuPercent) : null;
  const refreshedAt = overview?.collectedAt ?? metrics?.scrapedAt;
  const memoryLabel = getMemoryEstimateLabel(total);

  if (!metrics && !overview) {
    return (
      <div className="rounded-xl border border-slate-100 bg-slate-50/70 p-3">
        <div className="flex items-center justify-between">
          <div className="text-sm font-medium text-slate-700">🖥️ 系统状态</div>
          <div className="text-[11px] text-slate-400">指标加载中</div>
        </div>
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={onClick}
      className="w-full rounded-xl border border-slate-100 bg-slate-50/70 p-3 text-left transition hover:bg-slate-100/80"
    >
      <div className="flex items-center justify-between">
        <div className="text-sm font-medium text-slate-700">🖥️ 系统状态</div>
        <div className="flex items-center gap-2">
          <div className="text-[11px] text-slate-400">刷新于 {refreshedAt ? formatAge(refreshedAt) : "—"}</div>
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

      <div className="mt-3 grid grid-cols-2 gap-2">
        <StatusStat label={memoryLabel} value={memoryValue ?? "—"} />
        <StatusStat label="CPU" value={cpuValue ?? "—"} highlight />
      </div>
    </button>
  );
}

function SystemStatusModal({
  isOpen,
  onClose,
  overview,
  metrics,
}: {
  isOpen: boolean;
  onClose: () => void;
  overview: SystemOverview | null | undefined;
  metrics: SystemMetrics | null | undefined;
}) {
  const [selectedSection, setSelectedSection] = useState<"overview" | "ticks" | "llm">("overview");
  const totalTicks = metrics
    ? metrics.tickTotal.inlineSuccess +
      metrics.tickTotal.inlineError +
      metrics.tickTotal.isolatedSuccess +
      metrics.tickTotal.isolatedError
    : 0;
  const totalTokens = metrics
    ? metrics.llmTokensTotal.input +
      metrics.llmTokensTotal.output +
      metrics.llmTokensTotal.cacheRead +
      metrics.llmTokensTotal.cacheCreation
    : 0;
  const totalFailures = metrics
    ? metrics.tickTotal.inlineError + metrics.tickTotal.isolatedError
    : 0;
  const refreshedAt = overview?.collectedAt ?? metrics?.scrapedAt;
  const overviewTotal = overview?.components.total;
  const totalMemoryValue = overviewTotal
    ? formatComponentMemory(overviewTotal)
    : metrics
      ? formatBytes(metrics.processResidentMemoryBytes)
      : "—";
  const totalVmsValue = overviewTotal
    ? formatBytes(overviewTotal.vmsBytes)
    : metrics
      ? formatBytes(metrics.processVirtualMemoryBytes)
      : "—";
  const totalCpuValue = overviewTotal ? formatCpuPercent(overviewTotal.cpuPercent) : "—";
  const totalProcessCount = overviewTotal ? formatCount(overviewTotal.processCount) : "—";
  const totalMemoryLabel = getMemoryEstimateLabel(overviewTotal);
  const activeRunsValue = metrics ? formatCount(metrics.activeRuns) : "—";
  const backendMemoryValue = metrics ? formatBytes(metrics.processResidentMemoryBytes) : "—";
  const backendCpuSecondsValue = metrics ? `${metrics.processCpuSecondsTotal.toFixed(1)}s` : "—";
  const inlineSuccessValue = metrics ? formatCount(metrics.tickTotal.inlineSuccess) : "—";
  const isolatedSuccessValue = metrics ? formatCount(metrics.tickTotal.isolatedSuccess) : "—";
  const inlineErrorValue = metrics ? formatCount(metrics.tickTotal.inlineError) : "—";
  const isolatedErrorValue = metrics ? formatCount(metrics.tickTotal.isolatedError) : "—";
  const llmCallTotalValue = metrics ? formatCount(metrics.llmCallTotal) : "—";
  const inputCostCny = metrics
    ? calculateTokenCostCny(metrics.llmTokensTotal.input, TOKEN_PRICE_CNY_PER_MILLION.input)
    : 0;
  const outputCostCny = metrics
    ? calculateTokenCostCny(metrics.llmTokensTotal.output, TOKEN_PRICE_CNY_PER_MILLION.output)
    : 0;
  const cacheReadCostCny = metrics
    ? calculateTokenCostCny(metrics.llmTokensTotal.cacheRead, TOKEN_PRICE_CNY_PER_MILLION.cacheRead)
    : 0;
  const cacheCreationCostCny = metrics
    ? calculateTokenCostCny(
        metrics.llmTokensTotal.cacheCreation,
        TOKEN_PRICE_CNY_PER_MILLION.cacheCreation,
      )
    : 0;
  const llmCostTotalCny =
    inputCostCny + outputCostCny + cacheReadCostCny + cacheCreationCostCny;
  const llmCostValue = metrics ? formatCnyCost(llmCostTotalCny) : "—";
  const cacheTokenValue = metrics
    ? formatCount(metrics.llmTokensTotal.cacheRead + metrics.llmTokensTotal.cacheCreation)
    : "—";
  const inputTokenValue = metrics ? formatCount(metrics.llmTokensTotal.input) : "—";
  const outputTokenValue = metrics ? formatCount(metrics.llmTokensTotal.output) : "—";
  const cacheReadValue = metrics ? formatCount(metrics.llmTokensTotal.cacheRead) : "—";
  const cacheCreationValue = metrics ? formatCount(metrics.llmTokensTotal.cacheCreation) : "—";
  const sectionCounts = {
    overview: metrics ? 4 : 0,
    ticks: totalTicks,
    llm: metrics?.llmCallTotal ?? 0,
  };

  const modal = (
    <AnimatePresence>
      {isOpen && (
        <Modal
          isOpen={isOpen}
          onClose={onClose}
          variant="workspace"
          showCloseButton={false}
          title="系统状态"
          subtitle="查看运行时资源消耗和累计调用统计"
        >
          {!metrics && !overview ? (
            <div className="py-8 text-center text-sm text-slate-400">指标加载中</div>
          ) : (
            <WorkspaceModalShell
              sidebar={
                <>
                <div className="border-b border-slate-100 p-4">
                  <h3 className="text-sm font-semibold text-slate-700">🖥️ 资源摘要</h3>
                  <div className="mt-3 rounded-2xl bg-white p-4 shadow-xs">
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <div className="text-xs text-slate-500">{totalMemoryLabel}</div>
                        <div className="mt-1 text-lg font-semibold text-slate-900">
                          {totalMemoryValue}
                        </div>
                      </div>
                      <div>
                        <div className="text-xs text-slate-500">CPU</div>
                        <div className="mt-1 text-lg font-semibold text-emerald-600">
                          {totalCpuValue}
                        </div>
                      </div>
                    </div>
                    <div className="mt-3 flex items-center justify-between text-xs text-slate-500">
                      <span>活跃 Run</span>
                      <span className="font-semibold text-slate-700">
                        {overview ? totalProcessCount : activeRunsValue}
                      </span>
                    </div>
                    <div className="mt-2 flex items-center justify-between text-xs text-slate-500">
                      <span>最近刷新</span>
                      <span>{refreshedAt ? formatAge(refreshedAt) : "—"}</span>
                    </div>
                  </div>
                </div>

                <div className="flex-1 overflow-auto p-4">
                  <div className="mb-2 text-xs font-medium uppercase tracking-wider text-slate-400">
                    统计视图
                  </div>
                  <div className="space-y-1">
                    <NavItem
                      icon="📊"
                      label="资源总览"
                      count={sectionCounts.overview}
                      active={selectedSection === "overview"}
                      onClick={() => setSelectedSection("overview")}
                    />
                    <NavItem
                      icon="⏱️"
                      label="Tick 累计"
                      count={sectionCounts.ticks}
                      active={selectedSection === "ticks"}
                      onClick={() => setSelectedSection("ticks")}
                      tone={totalFailures > 0 ? "amber" : "slate"}
                    />
                    <NavItem
                      icon="🤖"
                      label="LLM 累计"
                      count={sectionCounts.llm}
                      active={selectedSection === "llm"}
                      onClick={() => setSelectedSection("llm")}
                      tone="emerald"
                    />
                  </div>
                </div>
                </>
              }
              contentClassName="overflow-y-auto p-6"
            >
                {selectedSection === "overview" && (
                  <div className="space-y-4">
                    <div className="grid grid-cols-2 gap-3">
                      <StatusStat label={totalMemoryLabel} value={totalMemoryValue} />
                      <StatusStat label="总虚拟内存" value={totalVmsValue} />
                      <StatusStat label="CPU" value={totalCpuValue} highlight />
                      <StatusStat label="总进程数" value={totalProcessCount} />
                    </div>
                    {overview ? (
                      <div className="rounded-2xl border border-slate-100 bg-slate-50/70 p-4">
                        <div className="text-sm font-semibold text-slate-700">组件拆分</div>
                        <div className="mt-3 space-y-3">
                          <ComponentStatusCard label="Backend" component={overview.components.backend} />
                          <ComponentStatusCard label="Frontend" component={overview.components.frontend} />
                          <ComponentStatusCard label="PostgreSQL" component={overview.components.postgres} />
                        </div>
                        <p className="mt-3 text-[11px] leading-5 text-slate-400">
                          PostgreSQL 优先展示更接近独占内存的估算值（USS/PSS），避免多进程共享页被 RSS 重复累计。
                        </p>
                      </div>
                    ) : (
                      <div className="rounded-2xl border border-slate-100 bg-slate-50/70 p-4">
                        <div className="text-sm font-semibold text-slate-700">当前观察</div>
                        <div className="mt-3 space-y-2 text-sm text-slate-600">
                          <div className="flex items-center justify-between rounded-xl bg-white px-3 py-2">
                            <span>后端进程内存</span>
                            <span className="font-medium text-slate-900">
                              {backendMemoryValue}
                            </span>
                          </div>
                          <div className="flex items-center justify-between rounded-xl bg-white px-3 py-2">
                            <span>后端 CPU 累计</span>
                            <span className="font-medium text-slate-900">
                              {backendCpuSecondsValue}
                            </span>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {selectedSection === "ticks" && (
                  <div className="space-y-4">
                    <div className="grid grid-cols-2 gap-3">
                      <MiniStatusChip label="总 Tick" value={formatCount(totalTicks)} />
                      <MiniStatusChip label="失败" value={formatCount(totalFailures)} tone="amber" />
                      <MiniStatusChip label="Inline 成功" value={inlineSuccessValue} />
                      <MiniStatusChip label="Isolated 成功" value={isolatedSuccessValue} />
                    </div>
                    <div className="rounded-2xl border border-slate-100 bg-slate-50/70 p-4">
                      <div className="text-sm font-semibold text-slate-700">执行拆分</div>
                      <div className="mt-3 space-y-2">
                        <StatusRow label="Inline 失败" value={inlineErrorValue} tone="amber" />
                        <StatusRow
                          label="Isolated 失败"
                          value={isolatedErrorValue}
                          tone="amber"
                        />
                        <StatusRow label="Inline 成功" value={inlineSuccessValue} />
                        <StatusRow label="Isolated 成功" value={isolatedSuccessValue} />
                      </div>
                    </div>
                  </div>
                )}

                {selectedSection === "llm" && (
                  <div className="space-y-4">
                    <div className="grid grid-cols-2 gap-3">
                      <MiniStatusChip label="调用次数" value={llmCallTotalValue} />
                      <MiniStatusChip label="总成本" value={llmCostValue} />
                      <MiniStatusChip label="总 Tokens" value={formatCount(totalTokens)} />
                      <MiniStatusChip
                        label="缓存 Tokens"
                        value={cacheTokenValue}
                      />
                    </div>
                    <div className="rounded-2xl border border-slate-100 bg-slate-50/70 p-4">
                      <div className="text-sm font-semibold text-slate-700">Token 明细</div>
                      <div className="mt-3 space-y-2">
                        <StatusRow label="输入 Tokens" value={inputTokenValue} />
                        <StatusRow label="输出 Tokens" value={outputTokenValue} />
                        <StatusRow label="缓存读取" value={cacheReadValue} />
                        <StatusRow
                          label="缓存创建"
                          value={cacheCreationValue}
                        />
                      </div>
                    </div>
                    <div className="rounded-2xl border border-slate-100 bg-slate-50/70 p-4">
                      <div className="text-sm font-semibold text-slate-700">费用明细（元 / 百万 tokens）</div>
                      <div className="mt-3 space-y-2">
                        <StatusRow
                          label={`输入 @ ${TOKEN_PRICE_CNY_PER_MILLION.input}`}
                          value={formatCnyCost(inputCostCny)}
                        />
                        <StatusRow
                          label={`输出 @ ${TOKEN_PRICE_CNY_PER_MILLION.output}`}
                          value={formatCnyCost(outputCostCny)}
                        />
                        <StatusRow
                          label={`缓存读取 @ ${TOKEN_PRICE_CNY_PER_MILLION.cacheRead}`}
                          value={formatCnyCost(cacheReadCostCny)}
                        />
                        <StatusRow
                          label={`缓存写入 @ ${TOKEN_PRICE_CNY_PER_MILLION.cacheCreation}`}
                          value={formatCnyCost(cacheCreationCostCny)}
                        />
                        <StatusRow label="合计" value={formatCnyCost(llmCostTotalCny)} />
                      </div>
                    </div>
                  </div>
                )}
            </WorkspaceModalShell>
          )}
        </Modal>
      )}
    </AnimatePresence>
  );

  if (typeof document === "undefined") return null;
  return createPortal(modal, document.body);
}

function StatusRow({
  label,
  value,
  tone = "slate",
}: {
  label: string;
  value: string;
  tone?: "slate" | "amber";
}) {
  return (
    <div className="flex items-center justify-between rounded-xl bg-white px-3 py-2">
      <span className="text-sm text-slate-600">{label}</span>
      <span className={`text-sm font-semibold ${tone === "amber" ? "text-amber-700" : "text-slate-900"}`}>
        {value}
      </span>
    </div>
  );
}

function ComponentStatusCard({
  label,
  component,
}: {
  label: string;
  component: SystemOverview["components"]["backend"];
}) {
  const unavailable = component.status === "unavailable";
  const memoryLabel = label === "PostgreSQL" ? "内存估算" : "内存";
  const memoryValue = label === "PostgreSQL" ? formatComponentMemory(component) : formatBytes(component.rssBytes);
  const memoryHint =
    label === "PostgreSQL" && component.uniqueBytes != null
      ? "优先 USS/PSS"
      : label === "PostgreSQL"
        ? "回退 RSS"
        : null;

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-xs">
      <div className="flex items-center justify-between">
        <div className="text-sm font-semibold text-slate-800">{label}</div>
        <span
          className={`rounded-full px-2.5 py-1 text-xs font-medium ${
            unavailable ? "bg-slate-100 text-slate-500" : "bg-emerald-50 text-emerald-700"
          }`}
        >
          {unavailable ? "未发现" : "已采集"}
        </span>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2">
        <MiniStatusChip label={memoryLabel} value={memoryValue} hint={memoryHint} />
        <MiniStatusChip label="CPU" value={formatCpuPercent(component.cpuPercent)} />
        <MiniStatusChip label="进程数" value={formatCount(component.processCount)} />
        <MiniStatusChip label="CPU 秒" value={component.cpuSeconds.toFixed(1)} />
      </div>
    </div>
  );
}

function StatusStat({
  label,
  value,
  highlight = false,
}: {
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <div
      className={`rounded-lg border p-2.5 ${
        highlight
          ? "border-emerald-100 bg-emerald-50/70"
          : "border-white/80 bg-white/80"
      }`}
    >
      <div className="text-[11px] text-slate-500">{label}</div>
      <div className="mt-1 text-sm font-semibold text-slate-800">{value}</div>
    </div>
  );
}

function MiniStatusChip({
  label,
  value,
  tone = "slate",
  hint,
}: {
  label: string;
  value: string;
  tone?: "slate" | "amber";
  hint?: string | null;
}) {
  const toneClasses =
    tone === "amber"
      ? "border-amber-100 bg-amber-50/80 text-amber-700"
      : "border-slate-100 bg-slate-50 text-slate-700";

  return (
    <div className={`rounded-lg border px-2.5 py-2 ${toneClasses}`}>
      <div className="text-[10px] opacity-70">{label}</div>
      <div className="mt-1 text-sm font-semibold">{value}</div>
      {hint ? <div className="mt-0.5 text-[10px] opacity-60">{hint}</div> : null}
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
          initial={false}
          animate={{ width: `${value}%` }}
          transition={{ duration: 0.2, ease: "easeOut" }}
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
          <span className="text-xs text-slate-500">待消费</span>
        </div>
      </div>

      {hasIssue && (
        <div className="mt-2 flex items-start gap-1.5 text-xs text-amber-600">
          <span>⚠️</span>
          <span>干预消费率较低，说明较多注入尚未被 tick 消费</span>
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
  locations?: Array<{ id: string; name: string; location_type: string }>;
}

type DirectorFilter = "all" | "queued" | "consumed" | "expired";

function DirectorInterventionModal({
  isOpen,
  onClose,
  stats,
  runId,
  onInjected,
  maxMemories,
  locations = [],
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
          variant="workspace"
          showCloseButton={false}
          title="🎬 导演干预控制台"
          subtitle="管理导演注入，并观察其待消费、已消费与过期状态"
        >
            <WorkspaceModalShell
              sidebar={
                <>
                <div className="border-b border-slate-100 p-4">
                  <DirectorEventForm
                    runId={runId}
                    onInjected={handleInjected}
                    compact
                    locations={locations}
                  />
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
                      label="待消费"
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

                {/* 消费率 */}
                <div className="border-t border-slate-100 p-4">
                  <div className="rounded-2xl bg-white p-4 shadow-xs">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-slate-500">消费率</span>
                      <span className={`font-bold ${hasIssue ? "text-amber-600" : "text-emerald-600"}`}>
                        {stats.executionRate}%
                      </span>
                    </div>
                    <div className="mt-2.5 h-2 overflow-hidden rounded-full bg-slate-100">
                      <motion.div
                        initial={false}
                        animate={{ width: `${stats.executionRate}%` }}
                        transition={{ duration: 0.2, ease: "easeOut" }}
                        className={`h-full rounded-full ${hasIssue ? "bg-amber-500" : "bg-emerald-500"}`}
                      />
                    </div>
                    {hasIssue && (
                      <p className="mt-2.5 text-xs text-amber-600">⚠️ 消费率较低</p>
                    )}
                  </div>
                </div>
                </>
              }
            >
                <div className="mb-4 flex items-center gap-2">
                  <span className="text-lg font-semibold text-ink">
                    {selectedFilter === "all" && "全部干预"}
                    {selectedFilter === "consumed" && "已消费"}
                    {selectedFilter === "queued" && "待消费"}
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
            </WorkspaceModalShell>
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
            label: "待消费",
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
