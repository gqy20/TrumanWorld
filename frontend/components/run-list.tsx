"use client";

import { usePathname, useRouter } from "next/navigation";
import { useState, useTransition, useRef, useCallback } from "react";
import { useDemoAccess } from "@/components/demo-access-provider";
import { deleteRunResult } from "@/lib/api";
import { useRuns } from "@/components/runs-provider";
import { formatRelativeTime } from "@/lib/time";
import { WorldOpeningAnimation } from "@/components/world-opening-animation";

type Run = {
  id: string;
  name: string;
  status: string;
  current_tick?: number;
  was_running_before_restart?: boolean;
  agent_count?: number;
  location_count?: number;
  event_count?: number;
  created_at?: string | null;
};

type RunListProps = {
  runs: Run[];
};

export function RunList({ runs }: RunListProps) {
  const router = useRouter();
  const pathname = usePathname();
  const { adminAuthorized, writeProtected } = useDemoAccess();
  const { refreshRuns } = useRuns();
  const [isPending, startTransition] = useTransition();
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [animationVisible, setAnimationVisible] = useState(false);
  const [animationRunName, setAnimationRunName] = useState("");
  const pendingRunId = useRef<string | null>(null);
  const canWrite = adminAuthorized || !writeProtected;

  const handleWorldClick = useCallback((run: Run) => {
    pendingRunId.current = run.id;
    setAnimationRunName(run.name);
    setAnimationVisible(true);
  }, []);

  const handleAnimationComplete = useCallback(() => {
    if (pendingRunId.current) {
      router.push(`/runs/${pendingRunId.current}/world`);
    }
  }, [router]);

  const handleDelete = (runId: string) => {
    if (!confirm("确定要删除这个模拟运行吗？此操作不可撤销。")) {
      return;
    }

    const isActiveRun = pathname.startsWith(`/runs/${runId}`);
    setDeletingId(runId);
    startTransition(async () => {
      if (isActiveRun) {
        router.push("/");
      }
      const result = await deleteRunResult(runId);
      if (result.data) {
        await refreshRuns();
      } else {
        alert(result.error === "network_error" ? "删除失败，后端当前不可达。" : "删除失败，请重试。");
      }
      setDeletingId(null);
    });
  };

  if (runs.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-[28px] border border-dashed border-slate-200 bg-white py-16 text-center">
        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-slate-50">
          <svg className="h-8 w-8 text-slate-300" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
          </svg>
        </div>
        <p className="mt-4 text-base font-medium text-slate-600">还没有运行</p>
        <p className="mt-1 text-sm text-slate-400">在上方创建第一个模拟运行</p>
      </div>
    );
  }

  return (
    <>
      <WorldOpeningAnimation
        isVisible={animationVisible}
        onComplete={handleAnimationComplete}
        runName={animationRunName}
        mode="enter"
      />
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
        {runs.map((run) => {
          const isRunning = run.status === "running";
          const isPaused = run.status === "paused";
          const statusBg = isRunning ? "bg-emerald-50/50" : isPaused ? "bg-amber-50/50" : "bg-slate-50/50";
          const statusBorder = isRunning ? "border-emerald-200/60" : isPaused ? "border-amber-200/60" : "border-slate-200/60";

          return (
            <div
              key={run.id}
              className={`group relative overflow-hidden rounded-[24px] border ${statusBorder} ${statusBg} shadow-xs backdrop-blur-sm transition-all duration-300 hover:-translate-y-1 hover:shadow-lg hover:bg-white/90`}
            >
            {/* 左侧状态竖条 */}
            <div
              className={`absolute left-0 top-0 h-full w-1 ${
                isRunning ? "bg-emerald-500" : isPaused ? "bg-amber-400" : "bg-slate-300"
              } ${isRunning ? "animate-pulse" : ""}`}
            />

            <div className="p-5 pl-6">
              {/* 头部：名称 + 删除按钮 */}
              <div className="flex items-start justify-between gap-2">
                <button
                  type="button"
                  onClick={() => handleWorldClick(run)}
                  className="min-w-0 flex-1 text-left"
                >
                  <h3 className="truncate text-lg font-semibold text-ink transition-colors group-hover:text-moss">
                    {run.name}
                  </h3>
                  <p className="mt-0.5 font-mono text-[10px] text-slate-400">{run.id.slice(0, 8)}…</p>
                </button>
                {canWrite ? (
                  <button
                    type="button"
                    onClick={() => handleDelete(run.id)}
                    disabled={isPending && deletingId === run.id}
                    className="shrink-0 rounded-lg p-1.5 text-slate-300 transition hover:bg-red-50 hover:text-red-400 disabled:opacity-50"
                    title="删除"
                  >
                    {deletingId === run.id ? (
                      <span className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-slate-200 border-t-red-400" />
                    ) : (
                      <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M3 6h18" /><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" /><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" />
                      </svg>
                    )}
                  </button>
                ) : null}
              </div>

              {/* Tick 号 - 大字体突出显示 */}
              <div className="mt-4 flex items-baseline gap-1">
                <span className="text-3xl font-bold tracking-tight text-ink">
                  {run.current_tick ?? 0}
                </span>
                <span className="text-xs text-slate-400">ticks</span>
              </div>
              {run.created_at && (
                <p className="mt-1 text-[11px] text-slate-400">
                  创建于 {formatRelativeTime(run.created_at, { maxUnit: "month" })}
                </p>
              )}

              {/* 状态标签 */}
              <div className="mt-3 flex items-center gap-2">
                <span
                  className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${
                    isRunning
                      ? "bg-emerald-100 text-emerald-700"
                      : isPaused
                      ? "bg-amber-100 text-amber-700"
                      : "bg-slate-100 text-slate-600"
                  }`}
                >
                  {isRunning && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-500" />}
                  {isRunning ? "运行中" : isPaused ? "已暂停" : run.status}
                </span>
                {run.was_running_before_restart && !isRunning && (
                  <span className="rounded-full bg-orange-100 px-2 py-0.5 text-xs font-medium text-orange-600">
                    待恢复
                  </span>
                )}
              </div>

              {/* 指标：人数 / 地点 / 事件 */}
              {(run.agent_count !== undefined || run.location_count !== undefined) && (
                <div className="mt-4 flex items-center gap-4 rounded-xl bg-white/60 px-3 py-2">
                  {run.agent_count !== undefined && (
                    <div className="flex items-center gap-1.5">
                      <span className="flex h-5 w-5 items-center justify-center rounded-md bg-moss/10 text-moss">
                        <svg className="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <circle cx="12" cy="8" r="3" /><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7" />
                        </svg>
                      </span>
                      <span className="text-xs text-slate-500">
                        <span className="font-semibold text-slate-700">{run.agent_count}</span> 角色
                      </span>
                    </div>
                  )}
                  {run.location_count !== undefined && (
                    <div className="flex items-center gap-1.5">
                      <span className="flex h-5 w-5 items-center justify-center rounded-md bg-sky/10 text-sky-600">
                        <svg className="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z" />
                        </svg>
                      </span>
                      <span className="text-xs text-slate-500">
                        <span className="font-semibold text-slate-700">{run.location_count}</span> 地点
                      </span>
                    </div>
                  )}
                  {run.event_count !== undefined && run.event_count > 0 && (
                    <div className="flex items-center gap-1.5">
                      <span className="flex h-5 w-5 items-center justify-center rounded-md bg-amber/10 text-amber-600">
                        <svg className="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
                        </svg>
                      </span>
                      <span className="text-xs text-slate-500">
                        <span className="font-semibold text-slate-700">{run.event_count}</span> 事件
                      </span>
                    </div>
                  )}
                </div>
              )}

              {/* 进入世界按钮 */}
              <button
                type="button"
                onClick={() => handleWorldClick(run)}
                className="mt-4 flex w-full items-center justify-center gap-2 rounded-xl bg-moss px-4 py-2.5 text-sm font-medium text-white shadow-xs transition-all hover:bg-moss/90 hover:shadow-md active:scale-[0.98]"
              >
                <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="9" /><path d="M12 3a15 15 0 0 1 0 18M3 12h18" />
                </svg>
                进入世界
              </button>
            </div>
            </div>
          );
        })}
      </div>
    </>
  );
}
