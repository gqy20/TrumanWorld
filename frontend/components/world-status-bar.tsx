"use client";

import { useState, useEffect, useRef } from "react";
import { useDemoAccess } from "@/components/demo-access-provider";
import { useWorld } from "@/components/world-context";
import { startRunResult, pauseRunResult } from "@/lib/api";
import { formatSimTime } from "@/lib/world-utils";

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
  const { runId, world, pulse, error, isValidating, updateRun, refresh } = useWorld();
  const { adminAuthorized, writeProtected } = useDemoAccess();
  const [isToggling, setIsToggling] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const activeRun = pulse?.run ?? world?.run;
  const activeWorldClock = pulse?.world_clock ?? world?.world_clock;
  const activeDailyStats = pulse?.daily_stats ?? world?.daily_stats;

  // 总时长 = elapsed_seconds(历史累计) + (now - started_at)(本次运行)
  // 暂停时仅展示 elapsed_seconds，不再递增
  // 惰性初始化：mount 时直接从已有 world 数据计算，避免从 0 闪烁
  // 注意：world 在 mount 时可能还是 null（SWR 异步加载），
  // 数据尚未到达时先显示 0，useEffect 会在 run 数据到达后立即修正。
  const [elapsed, setElapsed] = useState(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const isRunning = activeRun?.status === "running";
  const canWrite = adminAuthorized || !writeProtected;
  const startedAt = activeRun?.started_at;
  const elapsedBase = activeRun?.elapsed_seconds ?? 0;
  const simDay =
    activeRun == null
      ? 1
      : Math.floor(((activeRun.current_tick ?? 0) * (activeRun.tick_minutes ?? 5)) / 1440) + 1;

  useEffect(() => {
    if (isRunning) {
      if (startedAt) {
        // 有服务端时间戳：累计历史 + 本次运行时长
        const calcElapsed = () => {
          const startMs = new Date(startedAt).getTime();
          const sessionSecs = Math.floor((Date.now() - startMs) / 1000);
          // 如果 sessionSecs 异常大（超过 30 天），认为是崩溃脏数据，不叠加
          if (sessionSecs > 2592000) {
            setElapsed(elapsedBase);
          } else {
            setElapsed(elapsedBase + Math.max(0, sessionSecs));
          }
        };
        calcElapsed(); // 立即同步一次，避免刷新后从 0 闪烁
        if (!intervalRef.current) {
          intervalRef.current = setInterval(calcElapsed, 1000);
        }
      } else {
        // 服务端缺少启动时间时不伪造不可持久化的本地时长。
        setElapsed(elapsedBase);
      }
    } else {
      // 暂停：展示历史累计秒数，停止计时，立即同步
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

  if (!world && !pulse) {
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
      updateRun(result.data);
    } catch (err) {
      console.error("Failed to toggle run:", err);
    } finally {
      setIsToggling(false);
    }
  };

  return (
    <div className="flex items-center gap-3">
      {/* 模拟时间 - 移到暂停按钮左侧 */}
      <span className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-600">
        {activeWorldClock
          ? `第${simDay}天 ${activeWorldClock.weekday_name_cn} ${activeWorldClock.time}`
          : world
            ? `模拟时间 ${formatSimTime(world)}`
            : "模拟时间"}
      </span>

      {canWrite ? (
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
      ) : (
        <span className="inline-flex items-center rounded-full border border-amber-200 bg-amber-50 px-4 py-1.5 text-sm font-medium text-amber-800">
          只读演示
        </span>
      )}

      <span className="inline-flex min-w-[7.5rem] items-center justify-center gap-2 rounded-full bg-slate-900 px-3 py-1.5 text-sm text-white tabular-nums">
        <span
          className={`h-2 w-2 rounded-full ${isValidating ? "animate-pulse bg-emerald-300" : isRunning ? "bg-emerald-400" : "bg-slate-300"}`}
        />
        时间步 {activeRun?.current_tick ?? 0}
      </span>

      {/* Wall-clock elapsed time — only shown while running or just paused */}
      <span
        className={`inline-flex min-w-[6.5rem] items-center justify-center gap-1.5 rounded-full border px-3 py-1.5 text-sm tabular-nums ${
          isRunning
            ? "border-emerald-200 bg-emerald-50 text-emerald-700"
            : "border-slate-200 bg-slate-50 text-slate-400"
        }`}
        title="累计实际运行时长，暂停期间不计时"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-3.5 w-3.5 shrink-0">
          <circle cx="12" cy="12" r="10" />
          <polyline points="12 6 12 12 16 14" />
        </svg>
        {formatElapsed(elapsed)}
      </span>

      {/* Token 消耗统计 */}
      {(() => {
        const stats = activeDailyStats;
        if (!stats) return null;
        const totalTokens =
          (stats.total_input_tokens ?? 0) + (stats.total_output_tokens ?? 0);
        if (totalTokens === 0) return null;
        const totalM = (totalTokens / 1_000_000).toFixed(2);
        return (
          <span
            className="inline-flex min-w-[8.5rem] items-center justify-center gap-1.5 rounded-full border border-violet-200 bg-violet-50 px-3 py-1.5 text-sm text-violet-700 tabular-nums"
            title={`Input: ${(stats.total_input_tokens ?? 0).toLocaleString()} | Output: ${(stats.total_output_tokens ?? 0).toLocaleString()} | Reasoning: ${(stats.total_reasoning_tokens ?? 0).toLocaleString()} | Cache Read: ${(stats.total_cache_read_tokens ?? 0).toLocaleString()} | Cache Create: ${(stats.total_cache_creation_tokens ?? 0).toLocaleString()}`}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-3.5 w-3.5 shrink-0">
              <path d="M12 2L2 7l10 5 10-5-10-5z" />
              <path d="M2 17l10 5 10-5" />
              <path d="M2 12l10 5 10-5" />
            </svg>
            {totalM}M tokens
          </span>
        );
      })()}

      <button
        type="button"
        onClick={refresh}
        className="min-w-[4.75rem] rounded-full border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-600 transition hover:border-moss hover:text-moss"
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
