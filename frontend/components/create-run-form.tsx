"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition, useRef, useCallback } from "react";

import { createRunResult } from "@/lib/api";
import { useRuns } from "@/components/runs-provider";
import { WorldOpeningAnimation } from "@/components/world-opening-animation";

export function CreateRunForm() {
  const router = useRouter();
  const { refreshRuns } = useRuns();
  const [name, setName] = useState("demo-run");
  const [scenarioType, setScenarioType] = useState<"truman_world" | "open_world">("truman_world");
  const [tickMinutes, setTickMinutes] = useState(5);
  const [message, setMessage] = useState<string>("");
  const [isPending, startTransition] = useTransition();
  const [showAnimation, setShowAnimation] = useState(false);
  const [animationName, setAnimationName] = useState("");
  // 用 ref 保存待跳转的 runId，避免动画与创建完成的时序问题
  const pendingRunId = useRef<string | null>(null);
  const animationDone = useRef(false);
  const suggestions = ["demo-run", "town-morning", "story-lab", "night-shift"];

  const doNavigate = useCallback(() => {
    if (pendingRunId.current) {
      router.push(`/runs/${pendingRunId.current}/world`);
    }
  }, [router]);

  const handleAnimationComplete = useCallback(() => {
    animationDone.current = true;
    doNavigate();
  }, [doNavigate]);

  return (
    <>
      {/* 创建动画覆盖全屏 */}
      <WorldOpeningAnimation
        isVisible={showAnimation}
        onComplete={handleAnimationComplete}
        runName={animationName}
        mode="enter"
      />
    <form
      className="space-y-3"
      onSubmit={(event) => {
        event.preventDefault();
        // 立即启动动画
        setAnimationName(name);
        setShowAnimation(true);
        animationDone.current = false;
        pendingRunId.current = null;

        startTransition(async () => {
          const result = await createRunResult(name, scenarioType, true, tickMinutes);
          if (result.data) {
            await refreshRuns();
            pendingRunId.current = result.data.id;
            // 如果动画已经先播完，立即跳转
            if (animationDone.current) {
              doNavigate();
            }
            // 否则等动画 onComplete 时再跳转
          } else {
            // 创建失败：终止动画并显示错误
            setShowAnimation(false);
            setMessage(
              result.error === "network_error"
                ? "创建失败，后端当前不可达"
                : "创建失败，请稍后重试",
            );
          }
        });
      }}
    >
      {/* 名称输入行 */}
      <div className="flex items-center gap-2">
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          className="flex-1 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-base text-ink placeholder:text-slate-400 outline-hidden transition focus:border-moss focus:ring-2 focus:ring-moss/20"
          placeholder="输入模拟运行名称"
        />
        {/* 场景选择器 */}
        <div className="flex items-center gap-0.5 rounded-xl border border-slate-200 bg-slate-50 p-1">
          <button
            type="button"
            onClick={() => setScenarioType("truman_world")}
            className={`rounded-lg px-3 py-1.5 text-sm font-medium transition whitespace-nowrap ${
              scenarioType === "truman_world"
                ? "bg-moss text-white shadow-xs"
                : "text-slate-500 hover:bg-white hover:text-slate-700"
            }`}
          >
            Truman World
          </button>
          <button
            type="button"
            onClick={() => setScenarioType("open_world")}
            className={`rounded-lg px-3 py-1.5 text-sm font-medium transition whitespace-nowrap ${
              scenarioType === "open_world"
                ? "bg-moss text-white shadow-xs"
                : "text-slate-500 hover:bg-white hover:text-slate-700"
            }`}
          >
            Open World
          </button>
        </div>
        {/* 时间速度选择器 */}
        <div className="flex items-center gap-0.5 rounded-xl border border-slate-200 bg-slate-50 p-1">
          {([5, 15, 30, 60] as const).map((min) => (
            <button
              key={min}
              type="button"
              onClick={() => setTickMinutes(min)}
              className={`rounded-lg px-2.5 py-1.5 text-xs font-medium transition whitespace-nowrap ${
                tickMinutes === min
                  ? "bg-white text-slate-700 shadow-xs"
                  : "text-slate-400 hover:bg-white/60 hover:text-slate-600"
              }`}
            >
              {min}m
            </button>
          ))}
        </div>
        <button
          type="submit"
          disabled={isPending}
          className="inline-flex items-center gap-2 rounded-xl bg-moss px-5 py-2.5 text-sm font-semibold text-white shadow-xs transition hover:bg-moss/90 disabled:opacity-60 whitespace-nowrap"
        >
          {isPending ? (
            <>
              <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
              创建中...
            </>
          ) : (
            <>
              <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
              </svg>
              创建运行
            </>
          )}
        </button>
      </div>

      {/* 推荐命名 */}
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="text-xs text-slate-400">推荐：</span>
        {suggestions.map((suggestion) => (
          <button
            key={suggestion}
            type="button"
            onClick={() => setName(suggestion)}
            className="rounded-full border border-slate-200 bg-transparent px-2.5 py-0.5 text-xs text-slate-500 transition hover:border-moss hover:text-moss"
          >
            {suggestion}
          </button>
        ))}
      </div>

      {message && (
        <p
          className={`rounded-xl border px-4 py-3 text-sm ${
            message.includes("失败")
              ? "border-red-200 bg-red-50 text-red-700"
              : "border-emerald-200 bg-emerald-50 text-emerald-700"
          }`}
        >
          {message}
        </p>
      )}
    </form>
    </>
  );
}
