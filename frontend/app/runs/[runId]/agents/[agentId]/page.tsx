import Link from "next/link";

import { AgentAvatar } from "@/components/agent-avatar";
import {
  formatAgentScore,
  formatMemoryCategory,
  inferAgentStatus,
  memoryCategoryBadgeClass,
  relationshipTone,
} from "@/lib/agent-utils";
import { MetricChip } from "@/components/metric-chip";
import { getAgentResult, getWorldResult } from "@/lib/api";
import { describeAgentEvent } from "@/lib/event-utils";
import { tickToSimDayTime } from "@/lib/world-utils";
import {
  EVENT_CONVERSATION_JOINED,
  EVENT_CONVERSATION_STARTED,
  EVENT_LISTEN,
  EVENT_SPEECH,
} from "@/lib/simulation-protocol";

// 人格特质中文映射
const PERSONALITY_LABELS: Record<string, string> = {
  openness: "开放性",
  conscientiousness: "尽责性",
  extraversion: "外向性",
  agreeableness: "宜人性",
  neuroticism: "神经质",
  charisma: "魅力",
  humor: "幽默",
  empathy: "同理心",
  confidence: "自信",
  optimism: "乐观",
};

// 角色配置中文映射
const PROFILE_LABELS: Record<string, string> = {
  bio: "个人简介",
  world_role: "世界角色",
  workplace: "工作地点",
  work_description: "工作描述",
  home: "居住地",
  occupation: "职业",
  capabilities: "能力",
  model: "模型配置",
  work_schedule: "工作时间",
};

// 强制动态渲染，避免构建时获取数据
export const dynamic = "force-dynamic";

type AgentPageProps = {
  params: Promise<{ runId: string; agentId: string }>;
};

export default async function AgentPage({ params }: AgentPageProps) {
  const { runId, agentId } = await params;
  const [agentResult, worldResult] = await Promise.all([
    getAgentResult(runId, agentId),
    getWorldResult(runId),
  ]);
  const agent = agentResult.data;
  const world = worldResult.data;

  if (!agent) {
    return (
      <div className="flex h-full flex-col overflow-hidden bg-[radial-gradient(circle_at_top,#f7f3e8,#eef5f1_48%,#f8fafc)]">
        <div className="border-b border-white/60 bg-white/65 px-8 py-5 backdrop-blur-sm">
          <Link href={`/runs/${runId}/world`} className="group flex items-center gap-1.5 text-sm text-slate-500 hover:text-moss">
            <svg className="h-4 w-4 transition group-hover:-translate-x-0.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M15 18l-6-6 6-6" />
            </svg>
            <span>返回世界视图</span>
          </Link>
          <h1 className="mt-3 text-2xl font-semibold text-ink">未找到 Agent</h1>
        </div>
        <div className="flex flex-1 items-center justify-center">
          <p className="text-sm text-slate-500">
            {agentResult.error === "network_error"
              ? "后端当前不可达，请确认 API 服务已启动。"
              : "未获取到 agent 数据，可能是 agent 不存在。"}
          </p>
        </div>
      </div>
    );
  }

  const status = inferAgentStatus(agent.agent_id, agent.recent_events);

  return (
    <div className="flex h-full flex-col overflow-hidden bg-[radial-gradient(circle_at_top,#f7f3e8,#eef5f1_48%,#f8fafc)]">
      <div className="border-b border-white/60 bg-white/65 px-8 py-5 backdrop-blur-sm">
        <Link href={`/runs/${runId}/world`} className="group flex items-center gap-1.5 text-sm text-slate-500 hover:text-moss">
          <svg className="h-4 w-4 transition group-hover:-translate-x-0.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M15 18l-6-6 6-6" />
          </svg>
          <span>返回世界视图</span>
        </Link>
        <div className="mt-3 flex flex-wrap items-end justify-between gap-4">
          <div className="flex items-center gap-4">
            <AgentAvatar
              agentId={agent.agent_id}
              name={agent.name}
              occupation={agent.occupation}
              status={status}
              size="lg"
              configId={agent.config_id}
            />
            <div>
              <p className="text-xs uppercase tracking-[0.24em] text-slate-400">Resident Profile</p>
              <h1 className="mt-2 text-3xl font-semibold text-ink">{agent.name}</h1>
              <p className="mt-1 text-sm text-slate-500">
                {agent.occupation ?? "resident"} · 当前目标 {agent.current_goal ?? "暂无公开目标"}
              </p>
            </div>
          </div>
          <div className="rounded-full border border-white/70 bg-white/80 px-4 py-2 text-xs text-slate-600 shadow-xs">
            角色观察面板
          </div>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-8 py-6">
        <div className="space-y-6">
          <section className="rounded-[30px] border border-white/70 bg-white/78 p-6 shadow-xs backdrop-blur-sm">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="text-xs uppercase tracking-[0.22em] text-moss">角色概览</p>
                <h2 className="mt-2 text-2xl font-semibold text-ink">当前状态</h2>
                <p className="mt-1 max-w-2xl text-sm leading-6 text-slate-500">
                  这里汇总角色近期行为、记忆和关系，适合观察单个居民是如何理解世界并采取行动的。
                </p>
              </div>
              <div className="rounded-3xl border border-slate-200 bg-slate-50/80 px-4 py-3 text-right">
                <p className="text-xs uppercase tracking-[0.22em] text-slate-400">当前状态标签</p>
                <p className="mt-1 text-sm font-medium text-ink">{status}</p>
              </div>
            </div>

            <div className="mt-6 grid gap-3 md:grid-cols-5">
              <MetricChip label="Name" value={agent.name} />
              <MetricChip label="Occupation" value={agent.occupation ?? "-"} />
              <MetricChip label="Goal" value={agent.current_goal ?? "-"} />
              <MetricChip label="Events" value={agent.recent_events.length} />
              <MetricChip label="Links" value={agent.relationships.length} />
            </div>
          </section>

          <div className="grid gap-6 xl:grid-cols-[380px_minmax(0,1fr)]">
            <aside className="space-y-4">
              {/* 人设卡片 */}
              {(agent.personality && Object.keys(agent.personality).length > 0) || (agent.profile && Object.keys(agent.profile).length > 0) ? (
                <section className="rounded-[28px] border border-white/70 bg-white/80 p-5 shadow-xs backdrop-blur-sm">
                  <p className="text-xs uppercase tracking-[0.22em] text-slate-400">人设档案</p>
                  <h2 className="mt-2 text-xl font-semibold text-ink">角色设定</h2>

                  {agent.personality && Object.keys(agent.personality).length > 0 && (
                    <div className="mt-4">
                      <p className="text-xs font-medium text-slate-500">人格特质</p>
                      <div className="mt-2 space-y-2">
                        {Object.entries(agent.personality).map(([key, value]) => (
                          <div key={key} className="flex items-center justify-between">
                            <span className="text-sm text-slate-600">{PERSONALITY_LABELS[key] || key}</span>
                            <div className="flex items-center gap-2">
                              <div className="h-2 w-24 overflow-hidden rounded-full bg-slate-100">
                                <div
                                  className="h-full rounded-full bg-moss"
                                  style={{ width: `${(Number(value) || 0) * 100}%` }}
                                />
                              </div>
                              <span className="text-xs text-slate-500">{String(value)}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {agent.profile && Object.keys(agent.profile).length > 0 && (
                    <div className="mt-4">
                      <p className="text-xs font-medium text-slate-500">角色配置</p>
                      <div className="mt-2 space-y-1.5">
                        {Object.entries(agent.profile)
                          .filter(([key]) => !key.endsWith('_id') && key !== 'root_dir')
                          .map(([key, value]) => (
                          <div key={key} className="flex items-start justify-between text-sm">
                            <span className="text-slate-500">{PROFILE_LABELS[key] || key}</span>
                            <span className="text-right text-slate-700">{typeof value === 'object' ? JSON.stringify(value) : String(value)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </section>
              ) : null}

              <section className="rounded-[28px] border border-white/70 bg-white/80 p-5 shadow-xs backdrop-blur-sm">
                <p className="text-xs uppercase tracking-[0.22em] text-slate-400">关系网络</p>
                <h2 className="mt-2 text-xl font-semibold text-ink">{agent.relationships.length} 条关系</h2>
                <div className="mt-4 space-y-3">
                  {agent.relationships.length === 0 ? (
                    <p className="rounded-2xl bg-slate-50 px-4 py-4 text-sm text-slate-500">这个角色暂时没有公开关系数据。</p>
                  ) : (
                    agent.relationships.map((relationship) => (
                      <div key={relationship.other_agent_id} className="rounded-[24px] border border-slate-200 bg-white p-4 shadow-xs">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="text-sm font-semibold text-ink">
                              {relationship.other_agent_name || relationship.other_agent_id}
                            </p>
                            <p className="mt-1 text-xs uppercase tracking-[0.18em] text-slate-400">
                              {relationship.relation_type}
                            </p>
                          </div>
                          <span className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-[11px] text-slate-500">
                            familiar {relationship.familiarity.toFixed(2)}
                          </span>
                        </div>
                        <div className="mt-4 space-y-2">
                          <StatBar label="信任" value={relationship.trust} />
                          <StatBar label="亲近" value={relationship.affinity} />
                          <StatBar label="熟悉" value={relationship.familiarity} />
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </section>

              <section className="rounded-[28px] border border-slate-200 bg-slate-50/80 p-5">
                <p className="text-xs uppercase tracking-[0.22em] text-slate-400">阅读提示</p>
                <div className="mt-4 space-y-3 text-sm leading-6 text-slate-600">
                  <p>近期事件适合看“刚发生了什么”，记忆更适合看角色“是怎么记住这件事的”。</p>
                  <p>如果关系分数突然变化，通常可以回看最近对话或导演注入事件。</p>
                </div>
              </section>
            </aside>

            <div className="grid gap-6 xl:grid-cols-2">
              {/* 角色行为流 */}
              <section className="flex min-h-0 flex-col rounded-[28px] border border-white/70 bg-white/80 p-5 shadow-xs backdrop-blur-sm">
                <div className="mb-3 flex items-center justify-between gap-3">
                  <div>
                    <p className="text-xs uppercase tracking-[0.22em] text-slate-400">近期事件</p>
                    <h2 className="mt-1 text-lg font-semibold text-ink">角色行为流</h2>
                  </div>
                  <span className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs text-slate-500">
                    {agent.recent_events.length} 条
                  </span>
                </div>
            
                <div className="min-h-0 flex-1 space-y-1 overflow-y-auto pr-1">
                  {agent.recent_events.length === 0 ? (
                    <p className="rounded-2xl bg-slate-50 px-4 py-4 text-sm text-slate-500">暂无近期事件。</p>
                  ) : (
                    agent.recent_events.map((event) => {
                      const message = event.payload.message as string | undefined;
                      const isTalk =
                        event.event_type === "talk" || event.event_type === EVENT_SPEECH;
                      const isConversationStructure =
                        event.event_type === EVENT_CONVERSATION_STARTED ||
                        event.event_type === EVENT_CONVERSATION_JOINED;
                      const isListen = event.event_type === EVENT_LISTEN;
                      const isMove = event.event_type === "move";
                      const isNoise = event.event_type === "work" || event.event_type === "rest";
                      return (
                        <article
                          key={event.id}
                          className={`rounded-2xl px-3 py-2.5 ${
                            isTalk
                              ? "border border-sky-100 bg-sky-50/60"
                              : isConversationStructure
                              ? "border border-cyan-100 bg-cyan-50/50"
                              : isListen
                              ? "border border-fuchsia-100 bg-fuchsia-50/50"
                              : isMove
                              ? "border border-emerald-100 bg-emerald-50/50"
                              : isNoise
                              ? "bg-slate-50/70"
                              : "border border-slate-100 bg-white"
                          }`}
                        >
                          <div className="flex items-center justify-between gap-2">
                            <div className="flex min-w-0 items-center gap-2">
                              <span className={`shrink-0 text-[10px] font-medium uppercase tracking-wider ${
                                isTalk
                                  ? "text-sky-500"
                                  : isConversationStructure
                                  ? "text-cyan-600"
                                  : isListen
                                  ? "text-fuchsia-600"
                                  : isMove
                                  ? "text-emerald-600"
                                  : "text-slate-400"
                              }`}>
                                {event.event_type}
                              </span>
                              <span className={`truncate text-sm ${
                                isNoise ? "text-slate-400" : "text-ink"
                              }`}>
                                {describeAgentEvent(event)}
                              </span>
                            </div>
                            <span className="shrink-0 text-[11px] text-slate-400">
                                                          T{event.tick_no}
                                                          {world && (
                                                            <span className="ml-1 text-slate-300">
                                                              {tickToSimDayTime(
                                                                event.tick_no,
                                                                world.run.tick_minutes ?? 5,
                                                                world.run.current_tick ?? 0,
                                                                world.world_clock?.iso,
                                                              )}
                                                            </span>
                                                          )}
                                                        </span>
                          </div>
            
                          {isTalk && message ? (
                            <div className="mt-1.5 rounded-xl bg-white/80 px-3 py-2 text-sm italic text-slate-600">
                              &ldquo;{message}&rdquo;
                            </div>
                          ) : null}
            
                          {(event.target_name || event.location_name) && !isNoise ? (
                            <div className="mt-1.5 flex flex-wrap gap-1">
                              {event.target_name ? (
                                <span className="rounded-full border border-rose-100 bg-rose-50 px-2 py-0.5 text-[10px] text-rose-600">
                                  → {event.target_name}
                                </span>
                              ) : null}
                              {event.location_name ? (
                                <span className="rounded-full border border-slate-100 bg-slate-50 px-2 py-0.5 text-[10px] text-slate-500">
                                  📍 {event.location_name}
                                </span>
                              ) : null}
                            </div>
                          ) : null}
                        </article>
                      );
                    })
                  )}
                </div>
              </section>
            
              {/* 内部记忆栈 */}
              <section className="flex min-h-0 flex-col rounded-[28px] border border-white/70 bg-white/80 p-5 shadow-xs backdrop-blur-sm">
                <div className="mb-3 flex items-center justify-between gap-3">
                  <div>
                    <p className="text-xs uppercase tracking-[0.22em] text-slate-400">记忆</p>
                    <h2 className="mt-1 text-lg font-semibold text-ink">内部记忆栈</h2>
                  </div>
                  <span className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs text-slate-500">
                    {agent.memories.length} 条
                  </span>
                </div>
            
                <div className="min-h-0 flex-1 space-y-1 overflow-y-auto pr-1">
                  {agent.memories.length === 0 ? (
                    <p className="rounded-2xl bg-slate-50 px-4 py-4 text-sm text-slate-500">暂无记忆数据。</p>
                  ) : (
                    agent.memories.map((memory) => {
                      const isLowSignal = (memory.importance ?? 0) === 0;
                      return (
                        <article
                          key={memory.id}
                          className={`rounded-2xl px-3 py-2.5 ${
                            isLowSignal ? "bg-slate-50/70" : "border border-violet-100 bg-violet-50/50"
                          }`}
                        >
                          <div className="flex items-start justify-between gap-2">
                            <p className={`text-sm leading-5 ${
                              isLowSignal ? "text-slate-400" : "text-ink"
                            }`}>
                              {memory.content}
                            </p>
                            <div className="flex shrink-0 flex-col items-end gap-1">
                              {!isLowSignal && (
                                <span className="rounded-full border border-violet-200 bg-violet-50 px-2 py-0.5 text-[10px] text-violet-600">
                                  ★ {formatAgentScore(memory.importance)}
                                </span>
                              )}
                              <span
                                className={`rounded-full border px-2 py-0.5 text-[10px] ${memoryCategoryBadgeClass(memory.memory_category)}`}
                              >
                                {formatMemoryCategory(memory.memory_category)}
                              </span>
                              {memory.related_agent_name ? (
                                <span className="rounded-full border border-rose-100 bg-rose-50 px-2 py-0.5 text-[10px] text-rose-600">
                                  {memory.related_agent_name}
                                </span>
                              ) : null}
                            </div>
                          </div>
                          <div className="mt-2 flex flex-wrap gap-2 text-[10px] text-slate-500">
                            {(memory.streak_count ?? 1) > 1 ? (
                              <span>连续 {memory.streak_count} 次</span>
                            ) : null}
                            <span>事件显著性 {formatAgentScore(memory.event_importance)}</span>
                            <span>主体相关性 {formatAgentScore(memory.self_relevance)}</span>
                          </div>
                        </article>
                      );
                    })
                  )}
                </div>
              </section>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function StatBar({ label, value }: { label: string; value: number }) {
  const percentage = Math.max(0, Math.min(100, value * 100));

  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-xs text-slate-500">
        <span>{label}</span>
        <span>{value.toFixed(2)}</span>
      </div>
      <div className="h-2 rounded-full bg-slate-100">
        <div
          className={`h-2 rounded-full ${relationshipTone(value)}`}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}
