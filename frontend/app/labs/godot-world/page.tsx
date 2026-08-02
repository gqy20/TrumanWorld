import { GodotWorldHost } from "@/components/godot/godot-world-host";

export default function GodotWorldLabPage() {
  return (
    <main className="min-h-screen overflow-y-auto bg-[radial-gradient(circle_at_top_left,#dbe9df,#eef3ea_42%,#e8edf4)] p-4 sm:p-6 lg:h-full lg:min-h-0">
      <div className="mx-auto flex max-w-[1500px] flex-col gap-5">
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-xs font-semibold tracking-[0.22em] text-emerald-800 uppercase">
              Isolated Engineering Lab
            </p>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">
              Godot 具身世界 · Phase 0
            </h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
              使用录制快照验证 Godot Web、Next.js 宿主、版本化协议和角色选择闭环，不连接正式 Run。
            </p>
          </div>
          <span className="rounded-full border border-emerald-300 bg-emerald-50 px-3 py-1.5 text-xs font-medium text-emerald-800">
            protocol v1
          </span>
        </header>
        <GodotWorldHost />
      </div>
    </main>
  );
}
