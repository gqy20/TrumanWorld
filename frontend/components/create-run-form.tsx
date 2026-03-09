"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { createRunResult } from "@/lib/api";

export function CreateRunForm() {
  const router = useRouter();
  const [name, setName] = useState("demo-run");
  const [scenarioType, setScenarioType] = useState<"truman_world" | "open_world">("truman_world");
  const [tickMinutes, setTickMinutes] = useState(5);
  const [message, setMessage] = useState<string>("");
  const [isPending, startTransition] = useTransition();
  const suggestions = ["demo-run", "town-morning", "story-lab", "night-shift"];

  return (
    <form
      className="space-y-3"
      onSubmit={(event) => {
        event.preventDefault();
        startTransition(async () => {
          const result = await createRunResult(name, scenarioType, true, tickMinutes);
          if (result.data) {
            setMessage(`已创建：${result.data.name}`);
            router.push(`/runs/${result.data.id}?new=1`);
            router.refresh();
          } else {
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
          className="flex-1 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-base text-ink placeholder:text-slate-400 outline-none transition focus:border-moss focus:ring-2 focus:ring-moss/20"
          placeholder="输入模拟运行名称"
        />
        {/* 场景选择器 */}
        <div className="flex items-center gap-0.5 rounded-xl border border-slate-200 bg-slate-50 p-1">
          <button
            type="button"
            onClick={() => setScenarioType("truman_world")}
            className={`rounded-lg px-3 py-1.5 text-sm font-medium transition whitespace-nowrap ${
              scenarioType === "truman_world"
                ? "bg-moss text-white shadow-sm"
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
                ? "bg-moss text-white shadow-sm"
                : "text-slate-500 hover:bg-white hover:text-slate-700"
            }`}
          >
            Open World
          </button>
        </div>
        {/* 时间速度选择器 */}
        <select
          value={tickMinutes}
          onChange={(e) => setTickMinutes(Number(e.target.value))}
          className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-700 outline-none focus:border-moss focus:ring-2 focus:ring-moss/20"
        >
          <option value={1}>1分钟/tick</option>
          <option value={5}>5分钟/tick</option>
          <option value={10}>10分钟/tick</option>
          <option value={15}>15分钟/tick</option>
          <option value={30}>30分钟/tick</option>
          <option value={60}>60分钟/tick</option>
        </select>
        <button
          type="submit"
          disabled={isPending}
          className="inline-flex items-center gap-2 rounded-xl bg-moss px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-moss/90 disabled:opacity-60 whitespace-nowrap"
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
  );
}
