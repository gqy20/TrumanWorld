import { GodotWorldHost } from "@/components/godot/godot-world-host";

type Props = {
  searchParams: Promise<{ runId?: string }>;
};

export default async function GodotWorldLabPage({ searchParams }: Props) {
  const { runId } = await searchParams;
  return (
    <main className="min-h-screen overflow-y-auto bg-[radial-gradient(circle_at_top_left,#dbe9df,#eef3ea_42%,#e8edf4)] p-4 sm:p-6 lg:h-full lg:min-h-0">
      <div className="mx-auto flex max-w-[1500px] flex-col gap-5">
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-xs font-semibold tracking-[0.22em] text-emerald-800 uppercase">
              Isolated Engineering Lab
            </p>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">
              Godot 具身世界 · Phase 4
            </h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
              {runId
                ? `正在连接真实 Run ${runId}，通过世界快照和 SSE 同步权威活动、占用与队列。`
                : "未指定 runId，使用录制快照验证 Godot Web、版本化协议和角色选择闭环。"}
            </p>
          </div>
          <span className="rounded-full border border-emerald-300 bg-emerald-50 px-3 py-1.5 text-xs font-medium text-emerald-800">
            protocol v1
          </span>
        </header>
        <GodotWorldHost runId={runId} />
      </div>
    </main>
  );
}
