"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { deleteRun } from "@/lib/api";

type Run = {
  id: string;
  name: string;
  status: string;
  current_tick?: number;
  was_running_before_restart?: boolean;
  agent_count?: number;
  location_count?: number;
  event_count?: number;
};

type RunListProps = {
  runs: Run[];
};

export function RunList({ runs }: RunListProps) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const handleDelete = (runId: string) => {
    if (!confirm("确定要删除这个模拟运行吗？此操作不可撤销。")) {
      return;
    }

    setDeletingId(runId);
    startTransition(async () => {
      const result = await deleteRun(runId);
      if (result) {
        router.refresh();
      } else {
        alert("删除失败，请重试。");
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
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
      {runs.map((run) => {
        const isRunning = run.status === "running";
        const isPaused = run.status === "paused";
        const accentClass = isRunning
          ? "before:bg-emerald-500"
          : isPaused
          ? "before:bg-amber-400"
          : "before:bg-slate-300";
        return (
          <div
            key={run.id}
            className={`group relative overflow-hidden rounded-2xl border bg-white shadow-sm transition hover:-translate-y-0.5 hover:shadow-lg ${
              isRunning
                ? "border-emerald-200/80 hover:border-emerald-300"
                : isPaused
                ? "border-amber-200/80 hover:border-amber-300"
                : "border-slate-200 hover:border-slate-300"
            }`}
          >
            {/* 状态色条 */}
            <div
              className={`h-1 w-full ${
                isRunning ? "bg-emerald-500" : isPaused ? "bg-amber-400" : "bg-slate-200"
              } ${isRunning ? "animate-pulse" : ""}`}
            />

            <div className="p-4">
              {/* 名称行 + 删除 */}
              <div className="flex items-start gap-2">
                <Link href={`/runs/${run.id}`} className="min-w-0 flex-1">
                  <h3 className="truncate text-lg font-semibold text-ink transition-colors group-hover:text-moss">
                    {run.name}
                  </h3>
                  <p className="mt-0.5 font-mono text-xs text-slate-400">{run.id.slice(0, 8)}…</p>
                </Link>
                <button
                  type="button"
                  onClick={() => handleDelete(run.id)}
                  disabled={isPending && deletingId === run.id}
                  className="mt-1 flex-shrink-0 rounded-lg p-1.5 text-slate-300 transition hover:bg-red-50 hover:text-red-400 disabled:opacity-50"
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
              </div>

              {/* 状态 + Tick */}
              <div className="mt-3 flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <span
                    className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${
                      isRunning
                        ? "bg-emerald-50 text-emerald-700"
                        : isPaused
                        ? "bg-amber-50 text-amber-700"
                        : "bg-slate-100 text-slate-500"
                    }`}
                  >
                    {isRunning && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-500" />}
                    {isRunning ? "运行中" : isPaused ? "已暂停" : run.status}
                  </span>
                  {run.was_running_before_restart && (
                    <span className="rounded-full bg-orange-50 px-2 py-0.5 text-xs font-medium text-orange-600 ring-1 ring-orange-200">
                      待恢复
                    </span>
                  )}
                </div>
                <span className="rounded-md bg-slate-50 px-2 py-0.5 font-mono text-sm font-medium text-slate-500">
                  T{run.current_tick ?? 0}
                </span>
              </div>

              {/* 指标行：人数 / 地点 / 事件 */}
              {(run.agent_count !== undefined || run.location_count !== undefined) && (
                <div className="mt-3 flex items-center gap-3 border-t border-slate-100 pt-3">
                  {run.agent_count !== undefined && (
                    <div className="flex items-center gap-1 text-xs text-slate-500">
                      <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <circle cx="12" cy="8" r="4" /><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7" />
                      </svg>
                      <span className="font-medium text-slate-700">{run.agent_count}</span>
                      <span>角色</span>
                    </div>
                  )}
                  {run.location_count !== undefined && (
                    <div className="flex items-center gap-1 text-xs text-slate-500">
                      <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z" /><circle cx="12" cy="9" r="2.5" />
                      </svg>
                      <span className="font-medium text-slate-700">{run.location_count}</span>
                      <span>地点</span>
                    </div>
                  )}
                  {run.event_count !== undefined && run.event_count > 0 && (
                    <div className="flex items-center gap-1 text-xs text-slate-500">
                      <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
                      </svg>
                      <span className="font-medium text-slate-700">{run.event_count}</span>
                      <span>事件</span>
                    </div>
                  )}
                </div>
              )}

              {/* 操作按钮 */}
              <div className="mt-3 flex items-center gap-3 border-t border-slate-100 pt-3">
                <Link
                  href={`/runs/${run.id}`}
                  className="flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-moss/10 px-3 py-2 text-sm font-medium text-moss transition hover:bg-moss/20"
                >
                  <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" />
                  </svg>
                  总览
                </Link>
                <Link
                  href={`/runs/${run.id}/world`}
                  className="flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-500 transition hover:border-slate-300 hover:text-slate-700"
                >
                  <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="9" /><path d="M12 3a15 15 0 0 1 0 18M3 12h18" />
                  </svg>
                  世界
                </Link>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
