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
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault();
        startTransition(async () => {
          const result = await createRun(name, seedDemo);
          if (result) {
            setMessage(`已创建 run：${result.name} (${result.id})`);
            router.push(`/runs/${result.id}`);
            router.refresh();
          } else {
            setMessage("创建失败，可能是后端未启动。");
          }
        });
      }}
    >
      <label className="block space-y-2">
        <span className="text-sm font-medium text-ink">Run Name</span>
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          className="w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 text-sm outline-none ring-0 transition focus:border-moss"
          placeholder="输入新的 run 名称"
        />
      </label>
      <label className="flex items-center gap-3 text-sm text-slate-700">
        <input
          type="checkbox"
          checked={seedDemo}
          onChange={(event) => setSeedDemo(event.target.checked)}
          className="h-4 w-4 rounded border-slate-300 text-moss focus:ring-moss"
        />
        创建时自动注入 demo world
      </label>
      <button
        type="submit"
        disabled={isPending}
        className="inline-flex rounded-full bg-ink px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
      >
        {isPending ? "Creating..." : "Create Run"}
      </button>
      {message ? <p className="text-sm text-slate-600">{message}</p> : null}
    </form>
  );
}
