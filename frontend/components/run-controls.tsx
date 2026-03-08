"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { pauseRun, resumeRun, restoreAllRuns } from "@/lib/api";

type Run = { id: string; status: string; was_running_before_restart?: boolean };

type RunControlsProps = {
  runs: Run[];
};

export function RunControls({ runs }: RunControlsProps) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [busy, setBusy] = useState<"pause" | "resume" | "restore" | null>(null);

  const runningRuns = runs.filter((r) => r.status === "running");
  const pausedRuns = runs.filter((r) => r.status === "paused");
  const needsRestore = runs.filter((r) => r.was_running_before_restart);

  const handlePauseAll = () => {
    if (runningRuns.length === 0) return;
    setBusy("pause");
    startTransition(async () => {
      await Promise.all(runningRuns.map((r) => pauseRun(r.id)));
      setBusy(null);
      router.refresh();
    });
  };

  const handleResumeAll = () => {
    if (pausedRuns.length === 0 && needsRestore.length === 0) return;
    setBusy("resume");
    startTransition(async () => {
      const targets = pausedRuns.length > 0 ? pausedRuns : needsRestore;
      if (needsRestore.length > 0) {
        await restoreAllRuns();
      } else {
        await Promise.all(targets.map((r) => resumeRun(r.id)));
      }
      setBusy(null);
      router.refresh();
    });
  };

  if (runs.length === 0) return null;

  const canPause = runningRuns.length > 0;
  const canResume = pausedRuns.length > 0 || needsRestore.length > 0;

  return (
    <div className="flex items-center gap-3">
      {/* 运行状态统计 */}
      <div className="flex items-center gap-2 text-sm text-slate-500">
        {runningRuns.length > 0 && (
          <span className="flex items-center gap-1.5">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
            </span>
            <span className="font-medium text-emerald-700">{runningRuns.length} 运行中</span>
          </span>
        )}
        {runningRuns.length > 0 && (pausedRuns.length > 0 || needsRestore.length > 0) && (
          <span className="text-slate-300">·</span>
        )}
        {pausedRuns.length > 0 && (
          <span className="font-medium text-amber-600">{pausedRuns.length} 已暂停</span>
        )}
        {needsRestore.length > 0 && (
          <span className="font-medium text-orange-500">{needsRestore.length} 待恢复</span>
        )}
      </div>

      {/* 操作按钮 */}
      <div className="flex items-center gap-1.5">
        {canResume && (
          <button
            type="button"
            onClick={handleResumeAll}
            disabled={!!busy || isPending}
            className="flex items-center gap-1.5 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-xs font-medium text-emerald-700 transition hover:bg-emerald-100 disabled:opacity-50"
          >
            {busy === "resume" ? (
              <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-emerald-200 border-t-emerald-600" />
            ) : (
              <svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="currentColor">
                <polygon points="5 3 19 12 5 21 5 3" />
              </svg>
            )}
            全部开始
          </button>
        )}
        {canPause && (
          <button
            type="button"
            onClick={handlePauseAll}
            disabled={!!busy || isPending}
            className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-medium text-slate-600 transition hover:bg-slate-100 disabled:opacity-50"
          >
            {busy === "pause" ? (
              <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-slate-200 border-t-slate-500" />
            ) : (
              <svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="currentColor">
                <rect x="6" y="4" width="4" height="16" />
                <rect x="14" y="4" width="4" height="16" />
              </svg>
            )}
            全部暂停
          </button>
        )}
      </div>
    </div>
  );
}
