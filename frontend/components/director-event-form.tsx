"use client";

import { useState, useTransition } from "react";

import { injectDirectorEventResult } from "@/lib/api";

type DirectorEventFormProps = {
  runId: string;
  onInjected?: () => void;
  compact?: boolean;
};

export function DirectorEventForm({ runId, onInjected, compact }: DirectorEventFormProps) {
  const [eventType] = useState("broadcast");
  const [message, setMessage] = useState("Town hall at plaza");
  const [statusMessage, setStatusMessage] = useState("");
  const [isPending, startTransition] = useTransition();
  const presets = [
    "广场集合",
    "停电通知",
    "市集营业",
    "电影放映",
  ];

  return (
    <form
      className={compact ? "space-y-3" : "space-y-5"}
      onSubmit={(event) => {
        event.preventDefault();
        startTransition(async () => {
          const result = await injectDirectorEventResult(runId, {
            event_type: eventType,
            payload: { message },
            importance: 0.8,
          });
          setStatusMessage(
            result.data
              ? "已注入"
              : result.error === "network_error"
                ? "后端不可达"
                : "注入失败",
          );
          if (result.data) {
            onInjected?.();
          }
          setTimeout(() => setStatusMessage(""), 3000);
        });
      }}
    >
      {/* 标题 + 预设 */}
      {!compact && (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className="text-base font-medium text-ink">导演干预</span>
            <span className="rounded-full bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-600">广播全体</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {presets.map((preset) => (
              <button
                key={preset}
                type="button"
                onClick={() => setMessage(preset)}
                className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-600 transition hover:border-moss hover:bg-moss/5 hover:text-moss"
              >
                {preset}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* 表单字段 */}
      <div className="space-y-3">
        {!compact && (
          <label className="block">
            <span className="text-sm font-medium text-slate-600">事件内容</span>
          </label>
        )}
        <textarea
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          rows={compact ? 2 : 4}
          className="w-full resize-none rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm leading-relaxed outline-hidden transition placeholder:text-slate-400 hover:border-slate-300 focus:border-moss focus:ring-2 focus:ring-moss/10"
          placeholder="输入要广播给居民的消息..."
        />
        <input type="hidden" value={eventType} />
      </div>

      {/* 预设按钮（紧凑模式） */}
      {compact && (
        <div className="flex flex-wrap gap-1.5">
          {presets.map((preset) => (
            <button
              key={preset}
              type="button"
              onClick={() => setMessage(preset)}
              className="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs text-slate-600 transition hover:border-moss hover:bg-moss/5 hover:text-moss"
            >
              {preset}
            </button>
          ))}
        </div>
      )}

      {/* 提交 + 状态 */}
      <div className={`flex items-center gap-3 ${compact ? "" : "pt-2"}`}>
        <button
          type="submit"
          disabled={isPending}
          className={`rounded-full bg-ember font-medium text-white shadow-xs transition hover:bg-ember/90 hover:shadow-sm disabled:opacity-60 ${compact ? "px-4 py-1.5 text-xs" : "px-6 py-2.5 text-sm"}`}
        >
          {isPending ? "注入中..." : "注入事件"}
        </button>
        {statusMessage && (
          <span className={`text-xs font-medium ${statusMessage === "已注入" ? "text-emerald-600" : "text-red-500"}`}>
            {statusMessage === "已注入" ? "✓ " : "✗ "}{statusMessage}
          </span>
        )}
      </div>
    </form>
  );
}
