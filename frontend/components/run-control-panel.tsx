"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { advanceRunTick, pauseRun, resumeRun } from "@/lib/api";

type RunControlPanelProps = {
  runId: string;
  status?: string;
};

export function RunControlPanel({ runId, status }: RunControlPanelProps) {
  const router = useRouter();
  const [message, setMessage] = useState("");
  const [isPending, startTransition] = useTransition();

  const isRunning = status === "running";
  const isPaused = status === "paused";

  const handlePause = () => {
    startTransition(async () => {
      const result = await pauseRun(runId);
      if (!result) {
        setMessage("暂停失败，可能是后端未启动。");
        return;
      }
      setMessage("⏸️ 世界已暂停，居民活动停止");
      router.refresh();
    });
  };

  const handleResume = () => {
    startTransition(async () => {
      const result = await resumeRun(runId);
      if (!result) {
        setMessage("恢复失败，可能是后端未启动。");
        return;
      }
      setMessage("▶️ 世界已恢复运行");
      router.refresh();
    });
  };

  const handleStepTick = () => {
    startTransition(async () => {
      const result = await advanceRunTick(runId);
      if (!result) {
        setMessage("推进 tick 失败，可能是后端未启动。");
        return;
      }
      setMessage(
        `⏩ 手动推进 Tick ${result.tick_no}，accepted=${result.accepted_count}，rejected=${result.rejected_count}`
      );
      router.refresh();
    });
  };

  return (
    <div className="space-y-4">
      {/* 状态指示器 */}
      <div className="flex items-center gap-2">
        <span
          className={`h-3 w-3 rounded-full ${
            isRunning ? "animate-pulse bg-emerald-500" : "bg-amber-500"
          }`}
        />
        <span className="text-sm font-medium text-slate-700">
          {isRunning ? "🎬 世界运行中 - 居民自主活动" : "⏸️ 世界已暂停 - 导演控制模式"}
        </span>
      </div>

      {/* 导演控制按钮 */}
      <div className="flex flex-wrap gap-3">
        {isRunning ? (
          <button
            type="button"
            disabled={isPending}
            onClick={handlePause}
            className="inline-flex items-center gap-2 rounded-full bg-amber-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-amber-700 disabled:opacity-60"
          >
            <span>⏸️</span>
            <span>暂停世界</span>
          </button>
        ) : (
          <button
            type="button"
            disabled={isPending}
            onClick={handleResume}
            className="inline-flex items-center gap-2 rounded-full bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-emerald-700 disabled:opacity-60"
          >
            <span>▶️</span>
            <span>恢复运行</span>
          </button>
        )}

        <button
          type="button"
          disabled={isPending}
          onClick={handleStepTick}
          className="inline-flex items-center gap-2 rounded-full bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:opacity-60"
        >
          <span>⏭️</span>
          <span>手动推进一帧</span>
        </button>
      </div>

      {message ? (
        <p className="rounded-lg bg-slate-100 px-3 py-2 text-sm text-slate-700">
          {message}
        </p>
      ) : null}

      {/* 导演提示 */}
      <p className="text-xs text-slate-500">
        💡 提示：世界默认自动运行，导演可随时暂停观察或手动推进特定时刻
      </p>
    </div>
  );
}
