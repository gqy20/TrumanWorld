export default function HomePage() {
  return (
    <main className="min-h-screen px-6 py-12">
      <div className="mx-auto max-w-5xl space-y-8">
        <header className="space-y-4">
          <p className="text-sm uppercase tracking-[0.3em] text-moss">Director Console</p>
          <h1 className="text-5xl font-semibold">AI Truman World</h1>
          <p className="max-w-2xl text-lg text-slate-700">
            MVP 控制台骨架已就绪。下一步将在这里接入 run 状态、timeline 和 agent
            检视界面。
          </p>
        </header>
        <section className="grid gap-4 md:grid-cols-3">
          <div className="rounded-2xl bg-white p-5 shadow-sm">
            <h2 className="font-semibold">Runs</h2>
            <p className="mt-2 text-sm text-slate-600">查看和控制模拟运行。</p>
          </div>
          <div className="rounded-2xl bg-white p-5 shadow-sm">
            <h2 className="font-semibold">Timeline</h2>
            <p className="mt-2 text-sm text-slate-600">追踪事件流与导演注入事件。</p>
          </div>
          <div className="rounded-2xl bg-white p-5 shadow-sm">
            <h2 className="font-semibold">Agents</h2>
            <p className="mt-2 text-sm text-slate-600">检查单个 agent 的状态与记忆。</p>
          </div>
        </section>
      </div>
    </main>
  );
}

