"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { advanceRunTick, pauseRun, resumeRun, startRun } from "@/lib/api";

type RunControlPanelProps = {
  runId: string;
  status?: string;
};

export function RunControlPanel({ runId, status }: RunControlPanelProps) {
  const router = useRouter();
  const [message, setMessage] = useState("");
  const [isPending, startTransition] = useTransition();

  const handleAction = (action: "start" | "pause" | "resume") => {
    startTransition(async () => {
      const result =
        action === "start"
          ? await startRun(runId)
          : action === "pause"
            ? await pauseRun(runId)
            : await resumeRun(runId);

      if (!result) {
        setMessage("操作失败，可能是后端未启动。");
        return;
      }

      setMessage(`Run 状态已更新为 ${result.status}。`);
      router.refresh();
    });
  };

  const handleTick = () => {
    startTransition(async () => {
      const result = await advanceRunTick(runId);
      if (!result) {
        setMessage("推进 tick 失败，可能是后端未启动。");
        return;
      }

      setMessage(
        `Tick ${result.tick_no} 完成，accepted=${result.accepted_count}，rejected=${result.rejected_count}。`
      );
      router.refresh();
    });
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          disabled={isPending || status === "running"}
          onClick={() => handleAction("start")}
          className="inline-flex rounded-full bg-ink px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
        >
          {isPending ? "处理中..." : "Start Run"}
        </button>
        <button
          type="button"
          disabled={isPending || status !== "running"}
          onClick={() => handleAction("pause")}
          className="inline-flex rounded-full bg-slate-700 px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
        >
          Pause Run
        </button>
        <button
          type="button"
          disabled={isPending || status !== "paused"}
          onClick={() => handleAction("resume")}
          className="inline-flex rounded-full bg-moss px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
        >
          Resume Run
        </button>
        <button
          type="button"
          disabled={isPending || status === "draft"}
          onClick={handleTick}
          className="inline-flex rounded-full bg-ember px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
        >
          Step Tick
        </button>
      </div>
      {message ? <p className="text-sm text-slate-600">{message}</p> : null}
    </div>
  );
}
