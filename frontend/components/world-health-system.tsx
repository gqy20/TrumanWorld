"use client";

import { useState } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence } from "framer-motion";

import { Modal, WorkspaceModalShell } from "@/components/modal";
import { getLlmPricing } from "@/lib/llm-pricing";
import type { SystemMetrics, SystemOverview } from "@/lib/types";

interface SystemStatusPanelProps {
  overview: SystemOverview | null | undefined;
  metrics: SystemMetrics | null | undefined;
  llmModel?: string | null;
  onClick: () => void;
}

interface SystemStatusModalProps {
  isOpen: boolean;
  onClose: () => void;
  overview: SystemOverview | null | undefined;
  metrics: SystemMetrics | null | undefined;
  llmModel?: string | null;
}

export function SystemStatusPanel({
  overview,
  metrics,
  llmModel,
  onClick,
}: SystemStatusPanelProps) {
  const total = overview?.components.total;
  const memoryValue = total
    ? formatComponentMemory(total)
    : metrics
      ? formatBytes(metrics.processResidentMemoryBytes)
      : null;
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
          {llmModel ? (
            <div className="hidden rounded-full bg-white px-2 py-0.5 text-[11px] text-slate-500 md:block">
              {llmModel}
            </div>
          ) : null}
          <div className="text-[11px] text-slate-400">
            刷新于 {refreshedAt ? formatAge(refreshedAt) : "—"}
          </div>
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

export function SystemStatusModal({
  isOpen,
  onClose,
  overview,
  metrics,
  llmModel,
}: SystemStatusModalProps) {
  const [selectedSection, setSelectedSection] = useState<"overview" | "ticks" | "llm">(
    "overview"
  );
  const pricing = getLlmPricing(llmModel);
  const totalTicks = metrics
    ? metrics.tickTotal.inlineSuccess +
      metrics.tickTotal.inlineError +
      metrics.tickTotal.isolatedSuccess +
      metrics.tickTotal.isolatedError
    : 0;
  const totalTokens = metrics
    ? metrics.llmTokensTotal.input + metrics.llmTokensTotal.output
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
    ? calculateTokenCostCny(metrics.llmTokensTotal.input, pricing?.input ?? 0)
    : 0;
  const outputCostCny = metrics
    ? calculateTokenCostCny(metrics.llmTokensTotal.output, pricing?.output ?? 0)
    : 0;
  const cacheReadCostCny = metrics
    ? calculateTokenCostCny(metrics.llmTokensTotal.cacheRead, pricing?.cacheRead ?? 0)
    : 0;
  const cacheCreationCostCny = metrics
    ? calculateTokenCostCny(
        metrics.llmTokensTotal.cacheCreation,
        pricing?.cacheCreation ?? 0
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
                          <span className="font-medium text-slate-900">{backendMemoryValue}</span>
                        </div>
                        <div className="flex items-center justify-between rounded-xl bg-white px-3 py-2">
                          <span>后端 CPU 累计</span>
                          <span className="font-medium text-slate-900">{backendCpuSecondsValue}</span>
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
                      <StatusRow label="Isolated 失败" value={isolatedErrorValue} tone="amber" />
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
                    <MiniStatusChip label="总成本" value={pricing ? llmCostValue : "未配置"} />
                    <MiniStatusChip label="总 Tokens" value={formatCount(totalTokens)} />
                    <MiniStatusChip label="缓存 Tokens" value={cacheTokenValue} />
                  </div>
                  <div className="rounded-2xl border border-slate-100 bg-slate-50/70 p-4">
                    <div className="text-sm font-semibold text-slate-700">Token 明细</div>
                    <div className="mt-3 space-y-2">
                      <StatusRow label="输入 Tokens" value={inputTokenValue} />
                      <StatusRow label="输出 Tokens" value={outputTokenValue} />
                      <StatusRow label="缓存读取" value={cacheReadValue} />
                      <StatusRow label="缓存创建" value={cacheCreationValue} />
                    </div>
                  </div>
                  <div className="rounded-2xl border border-slate-100 bg-slate-50/70 p-4">
                    <div className="flex items-center justify-between text-sm font-semibold text-slate-700">
                      <span>费用明细（元 / 百万 tokens）</span>
                      <span className="text-xs font-medium text-slate-400">
                        {pricing ? `按 ${pricing.displayName}` : "当前模型未配置价格"}
                      </span>
                    </div>
                    <div className="mt-3 space-y-2">
                      <StatusRow
                        label={`输入 @ ${pricing?.input ?? 0}`}
                        value={formatCnyCost(inputCostCny)}
                      />
                      <StatusRow
                        label={`输出 @ ${pricing?.output ?? 0}`}
                        value={formatCnyCost(outputCostCny)}
                      />
                      <StatusRow
                        label={`缓存读取 @ ${pricing?.cacheRead ?? 0}`}
                        value={formatCnyCost(cacheReadCostCny)}
                      />
                      <StatusRow
                        label={`缓存写入 @ ${pricing?.cacheCreation ?? 0}`}
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
      <span
        className={`text-sm font-semibold ${tone === "amber" ? "text-amber-700" : "text-slate-900"}`}
      >
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
  const memoryValue =
    label === "PostgreSQL" ? formatComponentMemory(component) : formatBytes(component.rssBytes);
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
        highlight ? "border-emerald-100 bg-emerald-50/70" : "border-white/80 bg-white/80"
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
      <span
        className={`rounded-md px-2 py-0.5 text-xs font-semibold ${
          active
            ? tone === "emerald"
              ? "bg-emerald-100 text-emerald-800"
              : tone === "amber"
                ? "bg-amber-100 text-amber-800"
                : "bg-white text-slate-700 shadow-xs"
            : "bg-slate-100 text-slate-600"
        }`}
      >
        {count}
      </span>
    </button>
  );
}
