"use client";

import { useEffect } from "react";
import { reportApplicationError } from "@/lib/observability";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    reportApplicationError(error, {
      boundary: "global",
      digest: error.digest,
    });
  }, [error]);

  return (
    <html lang="zh-CN">
      <body className="flex min-h-screen items-center justify-center bg-slate-50 px-6 text-slate-700">
        <main className="max-w-md text-center">
          <p className="text-sm font-semibold uppercase tracking-[0.16em] text-slate-400">
            Truman World
          </p>
          <h1 className="mt-3 text-2xl font-semibold text-slate-800">界面暂时无法显示</h1>
          <p className="mt-2 text-sm text-slate-500">错误已经记录，请重试恢复当前页面。</p>
          <button
            type="button"
            onClick={reset}
            className="mt-6 rounded-full bg-slate-800 px-5 py-2.5 text-sm text-white transition hover:bg-slate-700"
          >
            重新加载
          </button>
        </main>
      </body>
    </html>
  );
}
