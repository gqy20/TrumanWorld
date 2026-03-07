import Link from "next/link";

import { MetricChip } from "@/components/metric-chip";
import { SectionCard } from "@/components/section-card";
import { getAgent } from "@/lib/api";

type AgentPageProps = {
  params: Promise<{ runId: string; agentId: string }>;
};

export default async function AgentPage({ params }: AgentPageProps) {
  const { runId, agentId } = await params;
  const agent = await getAgent(runId, agentId);

  return (
    <main className="min-h-screen px-6 py-12">
      <div className="mx-auto max-w-5xl space-y-8">
        <header className="space-y-3">
          <Link href={`/runs/${runId}`} className="text-sm uppercase tracking-[0.25em] text-moss">
            Run Detail
          </Link>
          <h1 className="text-4xl font-semibold text-ink">Agent {agentId}</h1>
          <p className="max-w-2xl text-slate-700">导演视角下的单体检视页，聚合状态、事件、记忆和关系。</p>
        </header>

        {agent ? (
          <>
            <SectionCard title="Current State" description="当前 agent 基本状态。">
              <div className="grid gap-4 md:grid-cols-5">
                <MetricChip label="Name" value={agent.name} />
                <MetricChip label="Occupation" value={agent.occupation ?? "-"} />
                <MetricChip label="Goal" value={agent.current_goal ?? "-"} />
                <MetricChip label="Events" value={agent.recent_events.length} />
                <MetricChip label="Relationships" value={agent.relationships.length} />
              </div>
            </SectionCard>

            <div className="grid gap-4 lg:grid-cols-2">
              <SectionCard title="Recent Events">
                <div className="space-y-3">
                  {agent.recent_events.length === 0 ? (
                    <p className="text-sm text-slate-600">暂无 recent events。</p>
                  ) : (
                    agent.recent_events.map((event) => (
                      <div key={event.id} className="rounded-2xl bg-mist px-4 py-3 text-sm">
                        <div className="font-medium text-ink">{event.event_type}</div>
                        <pre className="mt-2 whitespace-pre-wrap text-xs text-slate-700">
                          {JSON.stringify(event.payload, null, 2)}
                        </pre>
                      </div>
                    ))
                  )}
                </div>
              </SectionCard>

              <SectionCard title="Memories">
                <div className="space-y-3">
                  {agent.memories.length === 0 ? (
                    <p className="text-sm text-slate-600">暂无 memories。</p>
                  ) : (
                    agent.memories.map((memory) => (
                      <div key={memory.id} className="rounded-2xl bg-mist px-4 py-3 text-sm">
                        <div className="flex items-center justify-between gap-3">
                          <div className="font-medium text-ink">{memory.summary ?? memory.memory_type}</div>
                          <span className="text-xs uppercase tracking-[0.2em] text-slate-500">
                            {memory.memory_type}
                          </span>
                        </div>
                        <p className="mt-2 text-slate-700">{memory.content}</p>
                        <p className="mt-2 text-xs text-slate-500">
                          importance {memory.importance ?? 0}
                        </p>
                      </div>
                    ))
                  )}
                </div>
              </SectionCard>
            </div>

            <SectionCard title="Relationships">
              <div className="space-y-3">
                {agent.relationships.length === 0 ? (
                  <p className="text-sm text-slate-600">暂无 relationships。</p>
                ) : (
                  agent.relationships.map((relationship) => (
                    <div key={relationship.other_agent_id} className="rounded-2xl bg-mist px-4 py-3 text-sm">
                      <div className="flex items-center justify-between gap-3">
                        <div className="font-medium text-ink">{relationship.other_agent_id}</div>
                        <span className="rounded-full bg-white px-3 py-1 text-xs font-medium uppercase tracking-[0.18em] text-slate-600">
                          {relationship.relation_type}
                        </span>
                      </div>
                      <div className="mt-3 grid gap-3 md:grid-cols-3">
                        <div>
                          <div className="text-xs uppercase tracking-[0.16em] text-slate-500">Familiarity</div>
                          <div className="mt-1 text-base font-medium text-ink">{relationship.familiarity.toFixed(2)}</div>
                        </div>
                        <div>
                          <div className="text-xs uppercase tracking-[0.16em] text-slate-500">Trust</div>
                          <div className="mt-1 text-base font-medium text-ink">{relationship.trust.toFixed(2)}</div>
                        </div>
                        <div>
                          <div className="text-xs uppercase tracking-[0.16em] text-slate-500">Affinity</div>
                          <div className="mt-1 text-base font-medium text-ink">{relationship.affinity.toFixed(2)}</div>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </SectionCard>
          </>
        ) : (
          <SectionCard title="Unavailable">
            <p className="text-sm text-slate-600">未获取到 agent 数据，可能是后端未启动或 agent 不存在。</p>
          </SectionCard>
        )}
      </div>
    </main>
  );
}
