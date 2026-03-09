"use client";

import { useEffect, useState } from "react";
import { CreateRunForm } from "@/components/create-run-form";
import { RunList } from "@/components/run-list";
import { DeleteAllButton } from "@/components/delete-all-button";
import { RunControls } from "@/components/run-controls";
import type { RunSummary } from "@/lib/types";

type HomeViewProps = {
  runs: RunSummary[];
  error: string | null;
};

export function HomeView({ runs, error }: HomeViewProps) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    requestAnimationFrame(() => setVisible(true));
  }, []);

  const hasRuns = runs.length > 0;
  const runningCount = runs.filter((r) => r.status === "running").length;

  return (
    <div className="flex h-full flex-col overflow-hidden bg-[radial-gradient(circle_at_top,_#f7f3e8,_#eef5f1_48%,_#f8fafc)]">
      {/* 顶部 header - 毛玻璃效果 */}
      <div
        className={`flex-shrink-0 border-b border-white/60 bg-white/65 px-8 py-4 backdrop-blur transition-all duration-500 ${
          visible ? "opacity-100 translate-y-0" : "opacity-0 -translate-y-2"
        }`}
      >
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-ink">楚门的世界</h1>
            <p className="mt-0.5 text-sm text-slate-400">观察、记录、创造条件——让 Truman 真实地生活</p>
          </div>
          {hasRuns && (
            <div className="flex items-center gap-2 rounded-full border border-emerald-100 bg-emerald-50/80 px-3 py-1.5">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
              </span>
              <span className="text-xs font-medium text-emerald-700">{runningCount} 个运行中</span>
            </div>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        <div className="space-y-8 px-8 py-8">
          {/* 创建新模拟 */}
          <section
            className={`transition-all duration-500 delay-100 ${
              visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-3"
            }`}
          >
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-base font-semibold text-ink">创建世界</h2>
            </div>
            <div className="rounded-[28px] border border-white/70 bg-white/80 p-6 shadow-sm backdrop-blur">
              <CreateRunForm />
            </div>
          </section>

          {/* 运行列表 */}
          <section
            className={`transition-all duration-500 delay-200 ${
              visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-3"
            }`}
          >
            <div className="mb-4 flex items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <h2 className="text-base font-semibold text-ink">模拟运行</h2>
                {hasRuns && (
                  <span className="rounded-full bg-white/80 px-2.5 py-0.5 text-xs font-medium text-slate-500 shadow-sm">
                    {runs.length}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-3">
                <RunControls runs={runs} />
                {runs.length > 1 && <DeleteAllButton runs={runs} />}
              </div>
            </div>
            {error ? (
              <div className="mb-4 rounded-xl border border-amber-200 bg-amber-50/80 px-4 py-3 text-sm text-amber-800 backdrop-blur">
                {error === "network_error"
                  ? "后端当前不可达，列表展示的是空状态。"
                  : "运行列表加载失败。"}
              </div>
            ) : null}
            <RunList runs={runs} />
          </section>
        </div>
      </div>
    </div>
  );
}
