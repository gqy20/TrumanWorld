import Link from "next/link";

import { DirectorEventForm } from "@/components/director-event-form";
import { MetricChip } from "@/components/metric-chip";
import { RunControlPanel } from "@/components/run-control-panel";
import { SectionCard } from "@/components/section-card";
import { getRun, listAgents } from "@/lib/api";

type RunPageProps = {
  params: Promise<{ runId: string }>;
};

export default async function RunPage({ params }: RunPageProps) {
  const { runId } = await params;
  const [run, agentList] = await Promise.all([getRun(runId), listAgents(runId)]);

  return (
    <main className="min-h-screen px-6 py-12">
      <div className="mx-auto max-w-5xl space-y-8">
        <header className="space-y-3">
          <Link href="/" className="text-sm uppercase tracking-[0.25em] text-moss">
            Director Console
          </Link>
          <h1 className="text-4xl font-semibold text-ink">Run {runId}</h1>
          <p className="max-w-2xl text-slate-700">
            查看单个模拟运行的当前状态、tick 进度和下一步导航。
          </p>
        </header>

        <SectionCard title="Run Status" description="来自后端 `/runs/{id}` 的实时数据。">
          {run ? (
            <div className="space-y-6">
              <div className="grid gap-4 md:grid-cols-4">
                <MetricChip label="Name" value={run.name} />
                <MetricChip label="Status" value={run.status} />
                <MetricChip label="Tick" value={run.current_tick ?? "-"} />
                <MetricChip label="Tick Minutes" value={run.tick_minutes ?? "-"} />
              </div>
              <RunControlPanel runId={runId} status={run.status} />
            </div>
          ) : (
            <p className="text-sm text-slate-600">后端暂不可用，当前展示为占位状态。</p>
          )}
        </SectionCard>

        <div className="grid gap-4 md:grid-cols-2">
          <SectionCard title="Timeline" description="跳转到该 run 的事件时间线。">
            <Link
              href={`/runs/${runId}/timeline`}
              className="inline-flex rounded-full bg-ink px-4 py-2 text-sm font-medium text-white"
            >
              查看 Timeline
            </Link>
          </SectionCard>

          <SectionCard title="Agent Inspector" description="该 run 下已登记的 agents。">
            <div className="space-y-3">
              {agentList.agents.length === 0 ? (
                <p className="text-sm text-slate-600">当前 run 还没有 agents。</p>
              ) : (
                agentList.agents.map((agent) => (
                  <Link
                    key={agent.id}
                    href={`/runs/${runId}/agents/${agent.id}`}
                    className="flex items-center justify-between rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm transition hover:border-moss"
                  >
                    <span className="font-medium text-ink">{agent.name}</span>
                    <span className="text-slate-500">
                      {agent.occupation ?? "-"} · {agent.current_goal ?? "no-goal"}
                    </span>
                  </Link>
                ))
              )}
            </div>
          </SectionCard>
        </div>

        <SectionCard title="Director Event Injection" description="向世界注入一个简单事件。">
          <DirectorEventForm runId={runId} />
        </SectionCard>
      </div>
    </main>
  );
}
