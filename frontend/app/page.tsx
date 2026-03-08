import { CreateRunForm } from "@/components/create-run-form";
import { RunList } from "@/components/run-list";
import { DeleteAllButton } from "@/components/delete-all-button";
import { RunControls } from "@/components/run-controls";
import { listRuns } from "@/lib/api";

export default async function HomePage() {
  const runs = await listRuns();
  const hasRuns = runs.length > 0;
  const runningCount = runs.filter((r) => r.status === "running").length;

  return (
    <div className="flex h-full flex-col overflow-hidden">
      {/* 顶部 header */}
      <div className="flex-shrink-0 border-b border-slate-200/60 bg-white px-8 py-5">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold text-ink">控制台</h1>
          {hasRuns && (
            <div className="flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1.5 shadow-sm">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
              </span>
              <span className="text-xs font-medium text-slate-600">{runningCount} 个运行中</span>
            </div>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        <div className="space-y-8 p-8">
          {/* 创建新模拟 */}
          <section>
            <h2 className="mb-3 text-lg font-semibold text-ink">新建运行</h2>
            <div className="rounded-2xl border border-slate-200/80 bg-white/80 p-5 shadow-sm backdrop-blur-sm">
              <CreateRunForm />
            </div>
          </section>

          {/* 运行列表 */}
          <section>
            <div className="mb-4 flex items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <h2 className="text-lg font-semibold text-ink">模拟运行</h2>
                {hasRuns && (
                  <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-sm font-medium text-slate-500">
                    {runs.length}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-3">
                <RunControls runs={runs} />
                {runs.length > 1 && <DeleteAllButton runs={runs} />}
              </div>
            </div>
            <RunList runs={runs} />
          </section>
        </div>
      </div>
    </div>
  );
}

