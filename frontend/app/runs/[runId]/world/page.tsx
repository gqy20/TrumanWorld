"use client";

import { WorldCanvas } from "@/components/world-canvas";
import { WorldOpeningAnimation } from "@/components/world-opening-animation";
import { WorldStatusBar } from "@/components/world-status-bar";
import { useWorld } from "@/components/world-context";
import { useScenarioCatalog } from "@/hooks/use-scenario-catalog";
import { formatScenarioLabel } from "@/lib/scenario";

export default function WorldPage() {
  const { runId, world, error, refresh } = useWorld();
  const { scenarioNameMap } = useScenarioCatalog();

  if (error && !world) {
    return (
      <div className="flex h-full flex-col overflow-hidden bg-[radial-gradient(circle_at_top,#f7f3e8,#eef5f1_48%,#f8fafc)]">
        <div className="flex flex-1 items-center justify-center px-6">
          <div className="max-w-md rounded-2xl border border-amber-200 bg-white/80 p-6 text-center shadow-xs">
            <h1 className="text-xl font-semibold text-ink">世界加载失败</h1>
            <p className="mt-2 text-sm text-slate-600">
              {error === "network_error" ? "后端当前不可达，请确认 API 服务已启动。" : "未能获取世界快照。"}
            </p>
            <button
              type="button"
              onClick={refresh}
              className="mt-4 rounded-lg bg-ink px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-700"
            >
              重试
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (!world) {
    return (
      <div className="flex h-full min-h-screen flex-col overflow-hidden lg:min-h-0">
        <WorldOpeningAnimation />
      </div>
    );
  }

  const scenarioName =
    scenarioNameMap[world.run.scenario_type ?? ""] ?? formatScenarioLabel(world.run.scenario_type);

  return (
    <div className="flex min-h-screen flex-col overflow-x-hidden bg-[radial-gradient(circle_at_top,#f7f3e8,#eef5f1_48%,#f8fafc)] lg:h-full lg:min-h-0 lg:overflow-hidden">
        {/* 头部：标题 + 状态栏 */}
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-white/40 bg-white/55 px-4 py-3 backdrop-blur-sm sm:px-6">
        <div className="flex items-center gap-6">
          <div>
            <div className="mt-0.5 flex items-baseline gap-3">
              <h1 className="text-xl font-semibold text-ink">{world.run.name ?? "Run"}</h1>
              <span className="rounded-full border border-sky-200 bg-sky-50 px-2.5 py-1 text-[11px] font-medium text-sky-700">
                {scenarioName}
              </span>
            </div>
          </div>
        </div>
        <WorldStatusBar />
      </div>

      {/* 全屏地图区 */}
      <div className="min-h-0 flex-1 overflow-y-auto p-3 sm:p-4 lg:overflow-hidden">
        <WorldCanvas runId={runId} />
      </div>
    </div>
  );
}
