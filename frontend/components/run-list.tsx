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
    return <p className="text-sm text-slate-600">还没有 run，先创建一个新的模拟运行。</p>;
  }

  return (
    <div className="grid gap-3">
      {runs.map((run) => (
        <div
          key={run.id}
          className="group flex items-center justify-between rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm transition hover:border-moss"
        >
          <Link
            href={`/runs/${run.id}`}
            className="flex flex-1 items-center justify-between"
          >
            <span className="font-medium text-ink">{run.name}</span>
            <span className="text-slate-500">
              {run.status} · tick {run.current_tick ?? 0}
            </span>
          </Link>
          <button
            type="button"
            onClick={() => handleDelete(run.id)}
            disabled={isPending && deletingId === run.id}
            className="ml-3 rounded-lg p-2 text-slate-400 opacity-0 transition hover:bg-red-50 hover:text-red-500 group-hover:opacity-100 disabled:opacity-50"
            title="删除"
          >
            {deletingId === run.id ? (
              <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-red-500" />
            ) : (
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M3 6h18" />
                <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" />
                <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" />
              </svg>
            )}
          </button>
        </div>
      ))}
    </div>
  );
}
