"use client";

import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion } from "framer-motion";

import { DirectorEventForm } from "@/components/director-event-form";
import { ErrorState } from "@/components/error-state";
import { LoadingState } from "@/components/loading-state";
import { Modal, WorkspaceModalShell } from "@/components/modal";
import { getDirectorMemoriesResult, getDirectorObservationResult } from "@/lib/api";
import type { DirectorMemory, DirectorObservation } from "@/lib/types";

interface DirectorStatsProps {
  stats: {
    total: number;
    executed: number;
    executionRate: number;
  };
  onClick?: () => void;
}

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
  agentNameMap?: Record<string, string>;
}

type DirectorFilter = "all" | "queued" | "consumed" | "expired";

export function DirectorStats({ stats, onClick }: DirectorStatsProps) {
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
          <span className={`text-xs font-medium ${hasIssue ? "text-amber-600" : "text-slate-500"}`}>
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
          <span className="text-lg font-semibold text-slate-800">{stats.total}</span>
          <span className="text-xs text-slate-500">计划</span>
        </div>
        <div className="h-4 w-px bg-slate-200" />
        <div className="flex items-center gap-1.5">
          <span className="text-lg font-semibold text-emerald-600">{stats.executed}</span>
          <span className="text-xs text-slate-500">已消费</span>
        </div>
        <div className="h-4 w-px bg-slate-200" />
        <div className="flex items-center gap-1.5">
          <span className={`text-lg font-semibold ${hasIssue ? "text-amber-600" : "text-slate-600"}`}>
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

export function DirectorInterventionModal({
  isOpen,
  onClose,
  stats,
  runId,
  onInjected,
  maxMemories,
  locations = [],
  agentNameMap = {},
}: DirectorInterventionModalProps) {
  const [selectedFilter, setSelectedFilter] = useState<DirectorFilter>("all");
  const [memories, setMemories] = useState<DirectorMemory[]>([]);
  const [observation, setObservation] = useState<DirectorObservation | null>(null);
  const [isLoadingObservation, setIsLoadingObservation] = useState(false);
  const [observationError, setObservationError] = useState<string | null>(null);
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

    async function loadObservation() {
      setIsLoadingObservation(true);
      setObservationError(null);
      const result = await getDirectorObservationResult(runId);
      if (cancelled) return;
      if (result.data) {
        setObservation(result.data);
      } else {
        setObservation(null);
        setObservationError(result.error === "network_error" ? "后端不可达" : "观察结果加载失败");
      }
      setIsLoadingObservation(false);
    }

    void loadMemories();
    void loadObservation();

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
      const [memoriesResult, observationResult] = await Promise.all([
        getDirectorMemoriesResult(runId, maxMemories ?? 100),
        getDirectorObservationResult(runId),
      ]);
      if (memoriesResult.data) {
        setMemories(memoriesResult.data.memories);
      }
      if (observationResult.data) {
        setObservation(observationResult.data);
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

                <div className="flex-1 overflow-auto p-4">
                  <div className="mb-2 text-xs font-medium uppercase tracking-wider text-slate-400">
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
                    {hasIssue && <p className="mt-2.5 text-xs text-amber-600">⚠️ 消费率较低</p>}
                  </div>
                </div>
              </>
            }
          >
            <div className="mb-4">
              <DirectorObservationCard
                observation={observation}
                isLoading={isLoadingObservation}
                error={observationError}
                agentNameMap={agentNameMap}
                onRetry={() => {
                  void (async () => {
                    setIsLoadingObservation(true);
                    setObservationError(null);
                    const result = await getDirectorObservationResult(runId);
                    if (result.data) {
                      setObservation(result.data);
                    } else {
                      setObservation(null);
                      setObservationError(
                        result.error === "network_error" ? "后端不可达" : "观察结果加载失败"
                      );
                    }
                    setIsLoadingObservation(false);
                  })();
                }}
              />
            </div>

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
                filteredMemories.map((memory) => <DirectorMemoryCard key={memory.id} memory={memory} />)
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
        <span className="text-xs text-slate-400">{new Date(memory.created_at).toLocaleString()}</span>
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
        {memory.target_agent_names.length > 0 ? (
          <p>
            <span className="font-medium text-slate-700">执行对象：</span>
            {memory.target_agent_names.join("、")}
          </p>
        ) : null}
      </div>
    </div>
  );
}

function DirectorObservationCard({
  observation,
  isLoading,
  error,
  onRetry,
  agentNameMap = {},
}: {
  observation: DirectorObservation | null;
  isLoading: boolean;
  error: string | null;
  onRetry: () => void;
  agentNameMap?: Record<string, string>;
}) {
  if (isLoading) {
    return (
      <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-xs">
        <LoadingState message="正在加载导演观察..." size="sm" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-xs">
        <ErrorState message={error} onRetry={onRetry} size="sm" />
      </div>
    );
  }

  if (!observation) {
    return (
      <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-xs text-sm text-slate-500">
        暂无导演观察结果
      </div>
    );
  }

  const alertTone = observation.subject_alert_tracking_enabled
    ? "bg-amber-50 text-amber-700 border-amber-100"
    : "bg-slate-100 text-slate-700 border-slate-200";

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-xs">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-xs font-medium uppercase tracking-wider text-slate-400">导演观察</div>
          <div className="mt-1 text-base font-semibold text-slate-900">当前世界信号</div>
        </div>
        <span className={`rounded-full border px-2.5 py-1 text-xs font-medium ${alertTone}`}>
          {observation.subject_alert_tracking_enabled ? "主体告警已启用" : "主体告警未启用"}
        </span>
      </div>

      <div className="mt-3 grid gap-3 md:grid-cols-3">
        <ObservationMetric
          label="连续性风险"
          value={observation.continuity_risk}
          tone="text-slate-900"
        />
        <ObservationMetric
          label="怀疑级别"
          value={observation.suspicion_level}
          tone={observation.subject_alert_tracking_enabled ? "text-amber-700" : "text-slate-500"}
        />
        <ObservationMetric
          label="主体告警"
          value={
            observation.subject_alert_tracking_enabled && observation.subject_alert_score != null
              ? observation.subject_alert_score.toFixed(2)
              : "N/A"
          }
          tone={observation.subject_alert_tracking_enabled ? "text-amber-700" : "text-slate-500"}
        />
      </div>

      {observation.focus_agent_ids.length > 0 ? (
        <div className="mt-3 text-sm text-slate-600">
          <span className="font-medium text-slate-700">关注对象：</span>
          {observation.focus_agent_ids.map((id) => agentNameMap[id] ?? id).join("、")}
        </div>
      ) : null}

      {observation.notes.length > 0 ? (
        <div className="mt-3 rounded-xl bg-slate-50 px-3 py-2 text-sm text-slate-600">
          {observation.notes[0]}
        </div>
      ) : null}
    </div>
  );
}

function ObservationMetric({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: string;
}) {
  return (
    <div className="rounded-xl bg-slate-50 px-3 py-2">
      <div className="text-[11px] font-medium uppercase tracking-wider text-slate-400">{label}</div>
      <div className={`mt-1 text-sm font-semibold ${tone}`}>{value}</div>
    </div>
  );
}
