"use client";

import { useEffect, useState } from "react";
import { CreateRunForm } from "@/components/create-run-form";
import { RunList } from "@/components/run-list";
import { DeleteAllButton } from "@/components/delete-all-button";
import { useDemoAccess } from "@/components/demo-access-provider";
import { RunControls } from "@/components/run-controls";
import { useRuns } from "@/components/runs-provider";

export function HomeView() {
  const { runs, error } = useRuns();
  const { adminAuthorized, writeProtected } = useDemoAccess();
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    requestAnimationFrame(() => setVisible(true));
  }, []);

  const hasRuns = runs.length > 0;
  const runningCount = runs.filter((r) => r.status === "running").length;
  const canWrite = adminAuthorized || !writeProtected;

  return (
    <div className="flex h-full flex-col overflow-hidden bg-[radial-gradient(circle_at_top,#f7f3e8,#eef5f1_48%,#f8fafc)]">
      <div className="flex-1 overflow-y-auto">
        <div className="px-8 py-10">

          {/* 品牌标题区 */}
          <div
            className={`mb-8 transition-all duration-500 ${
              visible ? "opacity-100 translate-y-0" : "opacity-0 -translate-y-2"
            }`}
          >
            <div className="flex items-end justify-between">
              <div>
                <h1 className="text-2xl font-bold tracking-tight text-ink">楚门的世界</h1>
                <p className="mt-1 text-sm text-slate-400">观察、记录、创造条件——让 Truman 真实地生活</p>
              </div>
              <div className="flex items-center gap-3">
                {hasRuns && (
                  <div className="flex items-center gap-2 rounded-full border border-emerald-100 bg-emerald-50/80 px-3 py-1.5">
                    <span className="relative flex h-2 w-2">
                      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
                      <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
                    </span>
                    <span className="text-xs font-medium text-emerald-700">{runningCount} 个运行中</span>
                  </div>
                )}
                <a
                  href="https://github.com/gqy20/TrumanWorld"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex h-8 w-8 items-center justify-center rounded-full text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
                  title="查看 GitHub 仓库"
                >
                  <svg viewBox="0 0 24 24" fill="currentColor" className="h-5 w-5">
                    <path d="M12 2C6.477 2 2 6.477 2 12c0 4.419 2.865 8.166 6.839 9.489.5.092.682-.217.682-.482 0-.237-.008-.866-.013-1.7-2.782.603-3.369-1.342-3.369-1.342-.454-1.155-1.11-1.462-1.11-1.462-.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.087 2.91.831.092-.646.35-1.086.636-1.336-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.029-2.683-.103-.253-.446-1.27.098-2.647 0 0 .84-.269 2.75 1.025A9.578 9.578 0 0 1 12 6.836a9.59 9.59 0 0 1 2.504.337c1.909-1.294 2.747-1.025 2.747-1.025.546 1.377.203 2.394.1 2.647.64.699 1.028 1.592 1.028 2.683 0 3.842-2.339 4.687-4.566 4.935.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.743 0 .267.18.578.688.48C19.138 20.163 22 16.418 22 12c0-5.523-4.477-10-10-10z" />
                  </svg>
                </a>
              </div>
            </div>
          </div>

          {/* 只读提示 */}
          {!canWrite && (
            <div
              className={`mb-6 rounded-2xl border border-amber-200/80 bg-amber-50/70 px-5 py-4 text-sm text-amber-800 shadow-xs transition-all duration-500 delay-100 ${
                visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-3"
              }`}
            >
              当前为演示只读模式。你可以浏览世界、时间线和角色详情；创建、启动、暂停、删除与导演干预仅在解锁后可用。
            </div>
          )}

          {/* 统一容器：创建 + 运行列表 */}
          <div
            className={`rounded-[28px] border border-white/70 bg-white/80 shadow-xs backdrop-blur-sm transition-all duration-500 delay-100 ${
              visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-3"
            }`}
          >
            {/* 创建区 */}
            {canWrite && (
              <div className="border-b border-slate-100 px-6 py-5">
                <p className="mb-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">新建模拟</p>
                <CreateRunForm />
              </div>
            )}

            {/* 运行列表区 */}
            <div className="px-6 py-5">
              <div className="mb-4 flex items-center justify-between gap-4">
                <div className="flex items-center gap-2">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">模拟运行</p>
                  {hasRuns && (
                    <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-500">
                      {runs.length}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {canWrite ? <RunControls runs={runs} /> : null}
                  {canWrite && runs.length > 1 ? <DeleteAllButton runs={runs} /> : null}
                </div>
              </div>
              {error && (
                <div className="mb-4 rounded-xl border border-amber-200 bg-amber-50/80 px-4 py-3 text-sm text-amber-800">
                  {error === "network_error" ? "后端当前不可达，列表展示的是空状态。" : "运行列表加载失败。"}
                </div>
              )}
              <RunList runs={runs} />
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}
