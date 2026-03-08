"use client";

import { useState, useEffect, useRef } from "react";
import { useWorld } from "@/components/world-context";
import { startRunResult, pauseRunResult } from "@/lib/api";
import { formatSimTime, simDayLabel } from "@/lib/world-utils";

/** Format elapsed seconds as H:MM:SS or M:SS */
function formatElapsed(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) {
    return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  }
  return `${m}:${String(s).padStart(2, "0")}`;
}

export function WorldStatusBar() {
  const { runId, world, error, isValidating, refresh } = useWorld();
  const [isToggling, setIsToggling] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  // 总时长 = elapsed_seconds(历史累计) + (now - started_at)(本次运行)
  // 暂停时仅展示 elapsed_seconds，不再递增
  const [elapsed, setElapsed] = useState(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const localStartRef = useRef<number | null>(null);

  const isRunning = world?.run.status === "running";
  const startedAt = world?.run.started_at;
  const elapsedBase = world?.run.elapsed_seconds ?? 0;

  useEffect(() => {
    if (isRunning) {
      if (startedAt) {
        // 有服务端时间戳：累计历史 + 本次运行时长
        // 如果 started_at 距现超过 1 小时，说明是崩溃脂数据，跳过本次计算
        localStartRef.current = null;
        const calcElapsed = () => {
          const startMs = new Date(startedAt).getTime();
          const sessionSecs = Math.floor((Date.now() - startMs) / 1000);
          // 如果 sessionSecs 异常大（超过 2 小时），认为是崩溃脂数据，不叠加
          if (sessionSecs > 7200) {
            setElapsed(elapsedBase);
          } else {
            setElapsed(elapsedBase + Math.max(0, sessionSecs));
          }
        };
        calcElapsed();
        if (!intervalRef.current) {
          intervalRef.current = setInterval(calcElapsed, 1000);
        }
      } else {
        // 无服务端时间戳（旧数据）：本地从 elapsedBase 开始累加
        if (localStartRef.current === null) {
          localStartRef.current = Date.now();
        }
        if (!intervalRef.current) {
          intervalRef.current = setInterval(() => {
            const localSecs = Math.floor((Date.now() - localStartRef.current!) / 1000);
            setElapsed(elapsedBase + localSecs);
          }, 1000);
        }
      }
    } else {
      // 暂停：展示历史累计秒数，停止计时
      localStartRef.current = null;
      setElapsed(elapsedBase);
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    }
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [isRunning, startedAt, elapsedBase]);

  if (!world) {
    return (
      <div className="flex items-center gap-3">
        <span className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-400">
          加载中...
        </span>
      </div>
    );
  }

  const handleToggleRun = async () => {
    setIsToggling(true);
    try {
      const result = isRunning ? await pauseRunResult(runId) : await startRunResult(runId);
      if (!result.data) {
        setActionError(result.error === "network_error" ? "后端当前不可达" : "状态更新失败");
        return;
      } else {
        setActionError(null);
      }
      setTimeout(() => refresh(), 500);
    } catch (err) {
      console.error("Failed to toggle run:", err);
    } finally {
      setIsToggling(false);
    }
  };

  return (
    <div className="flex items-center gap-3">
      <button
        type="button"
        onClick={handleToggleRun}
        disabled={isToggling}
        className={`inline-flex items-center gap-1.5 rounded-full px-4 py-1.5 text-sm font-medium transition ${
          isRunning
            ? "bg-amber-100 text-amber-800 hover:bg-amber-200"
            : "bg-emerald-100 text-emerald-800 hover:bg-emerald-200"
        } ${isToggling ? "opacity-50 cursor-not-allowed" : ""}`}
        title={isRunning ? "暂停模拟" : "启动模拟"}
      >
        {isToggling ? (
          <svg className="h-3.5 w-3.5 animate-spin" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
        ) : isRunning ? (
          <svg viewBox="0 0 24 24" fill="currentColor" className="h-3.5 w-3.5">
            <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z" />
          </svg>
        ) : (
          <svg viewBox="0 0 24 24" fill="currentColor" className="h-3.5 w-3.5">
            <path d="M8 5v14l11-7z" />
          </svg>
        )}
        {isRunning ? "暂停" : "启动"}
      </button>

      <span className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-3 py-1.5 text-sm text-white">
        <span
          className={`h-2 w-2 rounded-full ${isValidating ? "animate-pulse bg-emerald-300" : isRunning ? "bg-emerald-400" : "bg-slate-300"}`}
        />
        Tick {world.run.current_tick ?? 0}
      </span>

      {/* Wall-clock elapsed time — only shown while running or just paused */}
      <span
        className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm ${
          isRunning
            ? "border-emerald-200 bg-emerald-50 text-emerald-700"
            : "border-slate-200 bg-slate-50 text-slate-400"
        }`}
        title="本次启动后的已运行时长（暂停时停止计时）"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-3.5 w-3.5 shrink-0">
          <circle cx="12" cy="12" r="10" />
          <polyline points="12 6 12 12 16 14" />
        </svg>
        {formatElapsed(elapsed)}
      </span>

      <span className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-600">
        {world.world_clock
          ? `${simDayLabel(world.run.current_tick ?? 0, world.run.tick_minutes ?? 5)} ${world.world_clock.time}`
          : `模拟时间 ${formatSimTime(world)}`}
      </span>

      <button
        type="button"
        onClick={refresh}
        className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-600 transition hover:border-moss hover:text-moss"
      >
        刷新
      </button>

      {error ? (
        <span className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1.5 text-sm text-amber-700">
          刷新失败
        </span>
      ) : null}
      {actionError ? (
        <span className="rounded-full border border-red-200 bg-red-50 px-3 py-1.5 text-sm text-red-700">
          {actionError}
        </span>
      ) : null}
    </div>
  );
}
