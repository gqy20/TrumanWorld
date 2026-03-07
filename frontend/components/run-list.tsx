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
};

type RunListProps = {
  runs: Run[];
  onDeleteAll?: () => void;
};

export function RunList({ runs, onDeleteAll }: RunListProps) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [isDeletingAll, setIsDeletingAll] = useState(false);

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

  const handleDeleteAll = () => {
    if (runs.length === 0) return;
    if (!confirm(`确定要删除全部 ${runs.length} 个模拟运行吗？此操作不可撤销。`)) {
      return;
    }
    setIsDeletingAll(true);
    startTransition(async () => {
      await Promise.all(runs.map((run) => deleteRun(run.id)));
      setIsDeletingAll(false);
      if (onDeleteAll) onDeleteAll();
      router.refresh();
    });
  };

  if (runs.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-white py-16 text-center">
        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-slate-50">
          <span className="text-3xl">🌱</span>
        </div>
        <p className="mt-4 text-sm font-medium text-slate-600">还没有运行</p>
        <p className="mt-1 text-xs text-slate-400">在上方创建第一个模拟运行</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* 运行卡片网格 */}
      <div className="grid gap-3 sm:grid-cols-2">
        {runs.map((run) => {
          const isRunning = run.status === "running";
          const isPaused = run.status === "paused";
          return (
            <div
              key={run.id}
              className="group relative overflow-hidden rounded-xl border border-slate-200 bg-white p-4 transition hover:border-moss hover:shadow-md"
            >
              {/* 顶部：名称和状态 */}
              <div className="flex items-start justify-between gap-3">
                <Link href={`/runs/${run.id}`} className="min-w-0 flex-1">
                  <h3 className="truncate font-medium text-ink group-hover:text-moss transition-colors">
                    {run.name}
                  </h3>
                  <p className="mt-1 text-xs text-slate-400">ID: {run.id.slice(0, 8)}</p>
                </Link>
                <div
                  className={`h-2.5 w-2.5 flex-shrink-0 rounded-full ${
                    isRunning
                      ? "animate-pulse bg-emerald-400"
                      : isPaused
                      ? "bg-amber-400"
                      : "bg-slate-300"
                  }`}
                />
              </div>

              {/* 中间：状态标签和 Tick */}
              <div className="mt-4 flex items-center justify-between">
                <span
                  className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                    isRunning
                      ? "bg-emerald-50 text-emerald-700"
                      : isPaused
                      ? "bg-amber-50 text-amber-700"
                      : "bg-slate-100 text-slate-500"
                  }`}
                >
                  {isRunning ? "运行中" : isPaused ? "已暂停" : run.status}
                </span>
                <span className="text-xs text-slate-400">
                  Tick <span className="font-medium text-slate-600">{run.current_tick ?? 0}</span>
                </span>
              </div>

              {/* 底部：操作按钮 */}
              <div className="mt-4 flex items-center justify-between border-t border-slate-100 pt-3">
                <Link
                  href={`/runs/${run.id}/world`}
                  className="text-xs text-moss hover:underline"
                >
                  查看世界 →
                </Link>
                <button
                  type="button"
                  onClick={() => handleDelete(run.id)}
                  disabled={isPending && deletingId === run.id}
                  className="flex items-center gap-1 rounded-lg px-2 py-1 text-xs text-slate-400 transition hover:bg-red-50 hover:text-red-500 disabled:opacity-50"
                  title="删除"
                >
                  {deletingId === run.id ? (
                    <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-slate-200 border-t-red-400" />
                  ) : (
                    <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M3 6h18" />
                      <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" />
                      <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" />
                    </svg>
                  )}
                  删除
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* 删除全部按钮 */}
      {runs.length > 1 && (
        <div className="flex justify-end pt-2">
          <button
            type="button"
            onClick={handleDeleteAll}
            disabled={isDeletingAll || isPending}
            className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs text-slate-400 transition hover:bg-red-50 hover:text-red-500 disabled:opacity-50"
          >
            {isDeletingAll ? (
              <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-slate-200 border-t-red-400" />
            ) : (
              <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M3 6h18" />
                <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" />
                <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" />
              </svg>
            )}
            删除全部
          </button>
        </div>
      )}
    </div>
  );
}
