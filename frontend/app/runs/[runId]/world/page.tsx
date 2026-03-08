import { WorldCanvas } from "@/components/world-canvas";
import { WorldProvider } from "@/components/world-context";
import { WorldStatusBar } from "@/components/world-status-bar";
import { getWorldResult } from "@/lib/api";

// 强制动态渲染，避免构建时获取数据
export const dynamic = "force-dynamic";

type WorldPageProps = {
  params: Promise<{ runId: string }>;
};

export default async function WorldPage({ params }: WorldPageProps) {
  const { runId } = await params;
  const initialWorld = await getWorldResult(runId);
  const initialData = initialWorld.data;

  if (!initialData) {
    return (
      <div className="flex h-full flex-col overflow-hidden bg-[radial-gradient(circle_at_top,_#f7f3e8,_#eef5f1_48%,_#f8fafc)]">
        <div className="flex flex-1 items-center justify-center px-6">
          <div className="max-w-md rounded-2xl border border-amber-200 bg-white/80 p-6 text-center shadow-sm">
            <h1 className="text-xl font-semibold text-ink">
              {initialWorld.error === "not_found" ? "未找到世界" : "世界加载失败"}
            </h1>
            <p className="mt-2 text-sm text-slate-600">
              {initialWorld.error === "network_error"
                ? "后端当前不可达，请确认 API 服务已启动。"
                : "未能获取世界快照。"}
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <WorldProvider runId={runId} initialData={initialData}>
      <div className="flex h-full flex-col overflow-hidden bg-[radial-gradient(circle_at_top,_#f7f3e8,_#eef5f1_48%,_#f8fafc)]">
        {/* 头部：标题 + 状态栏 */}
        <div className="flex flex-shrink-0 items-center justify-between border-b border-white/40 bg-white/55 px-6 py-3 backdrop-blur">
          <div className="flex items-center gap-6">
            <div>
              <div className="text-sm text-slate-500">{initialData?.run.name ?? "Run"}</div>
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
    </WorldProvider>
  );
}
