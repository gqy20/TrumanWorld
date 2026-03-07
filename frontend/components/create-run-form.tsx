"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { createRun } from "@/lib/api";

export function CreateRunForm() {
  const router = useRouter();
  const [name, setName] = useState("demo-run");
  const [seedDemo, setSeedDemo] = useState(true);
  const [message, setMessage] = useState<string>("");
  const [isPending, startTransition] = useTransition();

  return (
    <form
      className="flex flex-wrap items-end gap-4"
      onSubmit={(event) => {
        event.preventDefault();
        startTransition(async () => {
          const result = await createRun(name, seedDemo);
          if (result) {
            setMessage(`已创建：${result.name}`);
            router.push(`/runs/${result.id}`);
            router.refresh();
          } else {
            setMessage("创建失败，后端可能未启动");
          }
        });
      }}
    >
      <div className="flex-1 min-w-[200px]">
        <label className="block space-y-2">
          <span className="text-sm font-medium text-slate-200">模拟名称</span>
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            className="w-full rounded-xl border border-white/20 bg-white/10 px-4 py-2.5 text-sm text-white placeholder:text-slate-400 outline-none transition focus:border-moss focus:bg-white/20"
            placeholder="输入模拟运行名称"
          />
        </label>
      </div>

      <label className="flex items-center gap-2 text-sm text-slate-300 pb-3">
        <input
          type="checkbox"
          checked={seedDemo}
          onChange={(event) => setSeedDemo(event.target.checked)}
          className="h-4 w-4 rounded border-white/30 bg-white/10 text-moss focus:ring-moss focus:ring-offset-0"
        />
        使用 demo world
      </label>

      <button
        type="submit"
        disabled={isPending}
        className="inline-flex items-center gap-2 rounded-xl bg-moss px-5 py-2.5 text-sm font-medium text-white transition hover:bg-moss/90 disabled:opacity-60"
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

      {message && (
        <p className={`w-full text-sm ${message.includes("失败") ? "text-red-300" : "text-emerald-300"}`}>
          {message}
        </p>
      )}
    </form>
  );
}
