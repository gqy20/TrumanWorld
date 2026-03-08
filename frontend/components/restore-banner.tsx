"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { restoreAllRuns } from "@/lib/api";

type RestoreBannerProps = {
  count: number;
};

export function RestoreBanner({ count }: RestoreBannerProps) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [isRestoring, setIsRestoring] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  if (dismissed || count === 0) {
    return null;
  }

  const handleRestore = () => {
    setIsRestoring(true);
    startTransition(async () => {
      const result = await restoreAllRuns();
      setIsRestoring(false);
      if (result.length > 0) {
        router.refresh();
      } else {
        alert("恢复失败，请重试。");
      }
    });
  };

  return (
    <div className="flex items-center justify-between gap-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3">
      <div className="flex items-center gap-3">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="flex-shrink-0 text-amber-500"
        >
          <path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
          <path d="M3 3v5h5" />
          <path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16" />
          <path d="M16 21h5v-5" />
        </svg>
        <p className="text-sm text-amber-700">
          <span className="font-semibold">服务重启检测</span>
          <span className="ml-1.5 text-amber-600">
            发现 {count} 个运行在重启前正在运行，现已暂停。点击右侧按钮一键恢复。
          </span>
        </p>
      </div>
      <div className="flex flex-shrink-0 items-center gap-1.5">
        <button
          type="button"
          onClick={() => setDismissed(true)}
          disabled={isPending || isRestoring}
          className="rounded-lg px-2.5 py-1.5 text-sm font-medium text-amber-600 transition hover:bg-amber-100 disabled:opacity-50"
        >
          忽略
        </button>
        <button
          type="button"
          onClick={handleRestore}
          disabled={isPending || isRestoring}
          className="flex items-center gap-1.5 rounded-lg bg-amber-500 px-3 py-1.5 text-sm font-medium text-white shadow-sm transition hover:bg-amber-600 disabled:opacity-50"
        >
          {isRestoring ? (
            <>
              <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-white/30 border-t-white" />
              恢复中...
            </>
          ) : (
            <>
              <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polygon points="5 3 19 12 5 21 5 3" />
              </svg>
              恢复全部
            </>
          )}
        </button>
      </div>
    </div>
  );
}
