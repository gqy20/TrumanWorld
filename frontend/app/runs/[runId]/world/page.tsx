"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { useState, useEffect } from "react";
import { WorldCanvas } from "@/components/world-canvas";
import { WorldStatusBar } from "@/components/world-status-bar";
import { WorldOpeningAnimation } from "@/components/world-opening-animation";
import { useWorld } from "@/components/world-context";

export default function WorldPage() {
  const { runId, world, error } = useWorld();
  const searchParams = useSearchParams();
  const router = useRouter();
  const [showAnimation, setShowAnimation] = useState(false);

  // 检查是否是新建的世界
  useEffect(() => {
    const isNew = searchParams.get("new") === "1";
    if (isNew) {
      setShowAnimation(true);
      // 清除 URL 参数，避免刷新时再次显示
      router.replace(`/runs/${runId}/world`);
    }
  }, [searchParams, runId, router]);

  const handleAnimationComplete = () => {
    setShowAnimation(false);
  };

  if (error) {
    return (
      <div className="flex h-full flex-col overflow-hidden bg-[radial-gradient(circle_at_top,_#f7f3e8,_#eef5f1_48%,_#f8fafc)]">
        <div className="flex flex-1 items-center justify-center px-6">
          <div className="max-w-md rounded-2xl border border-amber-200 bg-white/80 p-6 text-center shadow-sm">
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
      <div className="flex h-full flex-col items-center justify-center overflow-hidden bg-[radial-gradient(circle_at_top,_#f7f3e8,_#eef5f1_48%,_#f8fafc)]">
        <div className="animate-pulse text-slate-400">加载中...</div>
      </div>
    );
  }

  return (
    <>
      {/* 开场动画 */}
      <WorldOpeningAnimation
        isVisible={showAnimation}
        onComplete={handleAnimationComplete}
        runName={world?.run.name}
      />

      <div className="flex h-full flex-col overflow-hidden bg-[radial-gradient(circle_at_top,_#f7f3e8,_#eef5f1_48%,_#f8fafc)]">
        {/* 头部：标题 + 状态栏 */}
      <div className="flex flex-shrink-0 items-center justify-between border-b border-white/40 bg-white/55 px-6 py-3 backdrop-blur">
        <div className="flex items-center gap-6">
          <div>
            <div className="text-sm text-slate-500">{world.run.name ?? "Run"}</div>
            <div className="mt-0.5 flex items-baseline gap-3">
              <h1 className="text-xl font-semibold text-ink">World Viewer</h1>
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
    </>
  );
}
