import { redirect } from "next/navigation";
import { getRunResult } from "@/lib/api";

// 强制动态渲染，避免构建时获取数据
export const dynamic = "force-dynamic";

type RunPageProps = {
  params: Promise<{ runId: string }>;
};

export default async function RunPage({ params }: RunPageProps) {
  const { runId } = await params;
  const runResult = await getRunResult(runId);

  if (!runResult.data) {
    // 如果运行不存在，显示错误页面
    const title = runResult.error === "not_found" ? "未找到 Run" : "Run 加载失败";
    const detail =
      runResult.error === "network_error"
        ? "后端当前不可达，请确认 API 服务已启动。"
        : runResult.error === "not_found"
          ? "这个运行不存在，或者已经被删除。"
          : "未能读取运行详情。";

    return (
      <div className="flex h-full flex-col overflow-hidden bg-[radial-gradient(circle_at_top_left,rgba(247,243,232,0.9),rgba(238,245,241,0.94)_38%,rgba(248,250,252,1))]">
        <div className="flex flex-1 items-center justify-center px-6">
          <div className="max-w-md rounded-2xl border border-amber-200 bg-white/80 p-6 text-center shadow-xs">
            <h1 className="text-xl font-semibold text-ink">{title}</h1>
            <p className="mt-2 text-sm text-slate-600">{detail}</p>
          </div>
        </div>
      </div>
    );
  }

  // 直接跳转到 World Viewer
  redirect(`/runs/${runId}/world`);
}
