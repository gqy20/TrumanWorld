"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, useTransition } from "react";

type WorldLiveControlsProps = {
  tick: number;
  status: string;
};

export function WorldLiveControls({ tick, status }: WorldLiveControlsProps) {
  const router = useRouter();
  const [isAutoRefresh, setIsAutoRefresh] = useState(false);
  const [isPending, startTransition] = useTransition();

  useEffect(() => {
    if (!isAutoRefresh) {
      return;
    }

    const timer = window.setInterval(() => {
      startTransition(() => {
        router.refresh();
      });
    }, 5000);

    return () => window.clearInterval(timer);
  }, [isAutoRefresh, router, startTransition]);

  return (
    <div className="flex flex-wrap items-center gap-3">
      <div className="rounded-full bg-white/80 px-4 py-2 text-sm text-slate-700 shadow-xs">
        Tick {tick} · {status}
      </div>
      <button
        type="button"
        onClick={() =>
          startTransition(() => {
            router.refresh();
          })
        }
        className="inline-flex rounded-full bg-ink px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
        disabled={isPending}
      >
        {isPending ? "刷新中..." : "Refresh"}
      </button>
      <label className="flex items-center gap-2 rounded-full bg-white/80 px-4 py-2 text-sm text-slate-700 shadow-xs">
        <input
          type="checkbox"
          checked={isAutoRefresh}
          onChange={(event) => setIsAutoRefresh(event.target.checked)}
          className="h-4 w-4 rounded-sm border-slate-300 text-moss focus:ring-moss"
        />
        Auto refresh
      </label>
    </div>
  );
}
