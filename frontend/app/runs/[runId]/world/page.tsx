"use client";

import { WorldCanvas } from "@/components/world-canvas";
import { WorldStatusBar } from "@/components/world-status-bar";
import { useWorld } from "@/components/world-context";

export default function WorldPage() {
  const { runId, world, error } = useWorld();

  if (error) {
    return (
      <div className="flex h-full flex-col overflow-hidden bg-[radial-gradient(circle_at_top,#f7f3e8,#eef5f1_48%,#f8fafc)]">
        <div className="flex flex-1 items-center justify-center px-6">
          <div className="max-w-md rounded-2xl border border-amber-200 bg-white/80 p-6 text-center shadow-xs">
            <h1 className="text-xl font-semibold text-ink">世界加载失败</h1>
            <p className="mt-2 text-sm text-slate-600">
              {error === "network_error" ? "后端当前不可达，请确认 API 服务已启动。" : "未能获取世界快照。"}
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (!world) {
    return (
      <div className="flex h-full flex-col items-center justify-center overflow-hidden bg-[radial-gradient(circle_at_top,#f7f3e8,#eef5f1_48%,#f8fafc)]">
        <div className="animate-pulse text-slate-400">加载中...</div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col overflow-hidden bg-[radial-gradient(circle_at_top,#f7f3e8,#eef5f1_48%,#f8fafc)]">
        {/* 头部：标题 + 状态栏 */}
      <div className="flex shrink-0 items-center justify-between border-b border-white/40 bg-white/55 px-6 py-3 backdrop-blur-sm">
        <div className="flex items-center gap-6">
          <div>
            <div className="mt-0.5 flex items-baseline gap-3">
              <h1 className="text-xl font-semibold text-ink">{world.run.name ?? "Run"}</h1>
              <span className="text-sm text-slate-500">地图与实时事件</span>
            </div>
          </div>
        </div>
        <WorldStatusBar />
      </div>

      {/* 全屏地图区 */}
      <div className="min-h-0 flex-1 overflow-hidden p-4">
        <WorldCanvas runId={runId} />
      </div>
    </div>
  );
}
