import { CreateRunForm } from "@/components/create-run-form";
import { RunList } from "@/components/run-list";
import { listRuns } from "@/lib/api";

export default async function HomePage() {
  const runs = await listRuns();
  const hasRuns = runs.length > 0;

  return (
    <div className="flex h-full flex-col overflow-hidden bg-slate-50">
      {/* 顶部标题栏 - 更简洁 */}
      <div className="flex-shrink-0 border-b border-slate-200 bg-white px-8 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-ink">控制台</h1>
            <p className="text-sm text-slate-500">管理和监控你的模拟世界</p>
          </div>
          {hasRuns && (
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2 text-sm text-slate-600">
                <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
                {runs.filter(r => r.status === "running").length} 个运行中
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 主内容区 */}
      <div className="flex-1 overflow-y-auto p-8">
        <div className="mx-auto max-w-5xl space-y-8">
          {/* 欢迎/创建区域 - 卡片式设计 */}
          <section className="overflow-hidden rounded-2xl bg-gradient-to-br from-ink to-slate-800 text-white shadow-lg">
            <div className="flex items-center justify-between p-8">
              <div className="space-y-2">
                <h2 className="text-2xl font-semibold">创建新模拟</h2>
                <p className="text-slate-300">启动一个新的虚拟世界，观察居民互动与故事发展</p>
              </div>
              <div className="hidden sm:block">
                <span className="text-5xl">🌍</span>
              </div>
            </div>
            <div className="border-t border-white/10 bg-white/5 px-8 py-6">
              <CreateRunForm />
            </div>
          </section>

          {/* 运行列表区域 */}
          <section>
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-ink">模拟运行</h2>
                <p className="text-sm text-slate-500">查看和管理所有模拟实例</p>
              </div>
              {hasRuns && (
                <span className="rounded-full bg-slate-200 px-3 py-1 text-xs font-medium text-slate-600">
                  共 {runs.length} 个
                </span>
              )}
            </div>
            <RunList runs={runs} />
          </section>
        </div>
      </div>
    </div>
  );
}
