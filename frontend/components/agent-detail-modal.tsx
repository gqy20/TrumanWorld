"use client";

import { useEffect, useState } from "react";
import { Modal } from "@/components/modal";
import { AgentAvatar } from "@/components/agent-avatar";
import {
  formatAgentScore,
  formatMemoryCategory,
  inferAgentStatus,
  memoryCategoryBadgeClass,
  relationshipTone,
} from "@/lib/agent-utils";
import { getAgentResult } from "@/lib/api";
import { formatRelativeTime } from "@/lib/time";
import { useWorld } from "@/components/world-context";
import { describeAgentEvent } from "@/lib/event-utils";
import { tickToSimDayTime } from "@/lib/world-utils";
import type { AgentDetails, AgentRecentEvent, AgentRelationship } from "@/lib/types";

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

interface AgentDetailModalProps {
  isOpen: boolean;
  onClose: () => void;
  runId: string;
  agentId: string;
}

export function AgentDetailModal({ isOpen, onClose, runId, agentId }: AgentDetailModalProps) {
  const { world } = useWorld();
  const [agent, setAgent] = useState<AgentDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAllRelationships, setShowAllRelationships] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    setLoading(true);
    setError(null);
    getAgentResult(runId, agentId)
      .then((agentRes) => {
        if (agentRes.data) {
          setAgent(agentRes.data);
          return;
        }
        setError(agentRes.error === "network_error" ? "网络错误" : "未找到智能体");
      })
      .catch(() => setError("加载失败"))
      .finally(() => setLoading(false));
  }, [isOpen, runId, agentId]);

  if (loading) {
    return (
      <Modal
        isOpen={isOpen}
        onClose={onClose}
        variant="inspector"
        showCloseButton={false}
        title="智能体详情"
      >
        <div className="flex h-64 items-center justify-center text-slate-400">
          <div className="mr-2 h-5 w-5 animate-spin rounded-full border-2 border-slate-200 border-t-moss" />
          加载中...
        </div>
      </Modal>
    );
  }

  if (error || !agent) {
    return (
      <Modal
        isOpen={isOpen}
        onClose={onClose}
        variant="panel"
        showCloseButton={false}
        title="智能体详情"
      >
        <div className="flex h-64 items-center justify-center text-amber-600">
          ⚠️ {error || "未找到智能体"}
        </div>
      </Modal>
    );
  }

  const status = inferAgentStatus(agent.agent_id, agent.recent_events);
  const personality = agent.personality || {};
  const profile = agent.profile || {};
  const relationships = agent.relationships || [];
  const memories = agent.memories || [];

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      variant="inspector"
      showCloseButton={false}
      title="智能体详情"
    >
      <div className="flex min-h-0 flex-1 overflow-hidden">
        {/* 左侧：基本信息 */}
        <aside className="flex w-80 shrink-0 flex-col border-r border-slate-100 bg-slate-50/50">
          <div className="flex-1 overflow-y-auto p-4">
            {/* 头像和状态 */}
            <section className="rounded-2xl border border-white/70 bg-white/80 p-4 shadow-xs backdrop-blur-sm">
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
                  <p className="text-lg font-semibold text-ink">{agent.name}</p>
                  <p className="text-sm text-slate-500">{agent.occupation || "居民"}</p>
                  <p className="mt-1 text-xs text-slate-400">
                    当前目标: {agent.current_goal || "无"}
                  </p>
                </div>
              </div>
            </section>

            {/* 人格特质 */}
            {Object.keys(personality).length > 0 && (
              <section className="mt-3 rounded-2xl border border-white/70 bg-white/80 p-4 shadow-xs backdrop-blur-sm">
                <p className="text-[11px] uppercase tracking-[0.15em] text-moss">人格特质</p>
                <div className="mt-3 space-y-2">
                  {Object.entries(personality).map(([key, value]) => (
                    <div key={key} className="flex items-center justify-between">
                      <span className="text-sm text-slate-600">
                        {PERSONALITY_LABELS[key] || key}
                      </span>
                      <div className="flex items-center gap-2">
                        <div className="h-1.5 w-16 overflow-hidden rounded-full bg-slate-100">
                          <div
                            className="h-full rounded-full bg-moss"
                            style={{ width: `${(value as number) * 100}%` }}
                          />
                        </div>
                        <span className="text-xs text-slate-500">
                          {(value as number).toFixed(1)}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* 角色配置 */}
            {Object.keys(profile).length > 0 && (
              <section className="mt-3 rounded-2xl border border-white/70 bg-white/80 p-4 shadow-xs backdrop-blur-sm">
                <p className="text-[11px] uppercase tracking-[0.15em] text-moss">角色设定</p>
                <div className="mt-3 space-y-2">
                  {Object.entries(profile).map(([key, value]) => (
                    <div key={key}>
                      <span className="text-[10px] text-slate-400">
                        {PROFILE_LABELS[key] || key}
                      </span>
                      <p className="text-sm text-slate-700">{String(value)}</p>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* 关系网络 */}
            {relationships.length > 0 && (
              <section className="mt-3 rounded-2xl border border-white/70 bg-white/80 p-4 shadow-xs backdrop-blur-sm">
                <p className="text-[11px] uppercase tracking-[0.15em] text-moss">
                  关系网络 ({relationships.length})
                </p>
                <div className="mt-3 space-y-3">
                  {(showAllRelationships ? relationships : relationships.slice(0, 5)).map((rel: AgentRelationship, index: number) => {
                    const familiarityPct = (rel.familiarity * 100).toFixed(0);
                    const barColor = relationshipTone(rel.familiarity);
                    const textColor = rel.familiarity >= 0.75
                      ? "text-emerald-600"
                      : rel.familiarity >= 0.45
                        ? "text-amber-600"
                        : "text-slate-500";
                    return (
                      <div key={`${rel.other_agent_id}-${index}`}>
                        <div className="flex items-center justify-between">
                          <span className="text-sm text-slate-700">{rel.other_agent_name || "未知"}</span>
                          <span className={`text-[10px] ${textColor}`}>
                            {familiarityPct}%
                          </span>
                        </div>
                        <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
                          <div
                            className={`h-full rounded-full ${barColor}`}
                            style={{ width: `${familiarityPct}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
                {relationships.length > 5 && (
                  <button
                    type="button"
                    onClick={() => setShowAllRelationships((v) => !v)}
                    className="mt-3 w-full rounded-lg border border-slate-200 bg-slate-50 py-1.5 text-xs text-slate-500 transition hover:bg-slate-100 hover:text-slate-700"
                  >
                    {showAllRelationships ? "收起" : `查看全部 ${relationships.length} 个关系`}
                  </button>
                )}
              </section>
            )}
          </div>
        </aside>

        {/* 右侧：行为和记忆 */}
        <div className="flex min-h-0 flex-1 flex-col gap-4 bg-slate-50/30 p-4">
          {/* 近期事件 */}
          <section className="flex min-h-0 flex-1 flex-col rounded-2xl border border-slate-200 bg-white p-4 shadow-xs">
            <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-700">
              <span className="h-4 w-1 rounded-full bg-moss" />
              近期事件
              <span className="ml-1 text-xs font-normal text-slate-400">({agent.recent_events.length})</span>
            </h3>
            <div className="flex-1 overflow-y-auto pr-1">
              {agent.recent_events.length === 0 ? (
                <p className="text-sm text-slate-400">暂无近期事件</p>
              ) : (
                <div className="space-y-1">
                  {agent.recent_events.map((event: AgentRecentEvent) => {
                    const isLowPriority = event.event_type === "work" || event.event_type === "rest";
                    const timeLabel = world
                      ? tickToSimDayTime(
                          event.tick_no,
                          world.run.tick_minutes ?? 5,
                          world.run.current_tick ?? 0,
                          world.world_clock?.iso
                        )
                      : null;
                    if (isLowPriority) {
                      return (
                        <div
                          key={event.id}
                          className="flex items-center gap-2 rounded-r border-l-2 border-slate-200 py-1 pl-2 pr-2 text-xs text-slate-500"
                        >
                          <span className="flex-1 truncate">{describeAgentEvent(event)}</span>
                          {timeLabel && <span className="shrink-0 text-slate-400">{timeLabel}</span>}
                        </div>
                      );
                    }
                    const evtStr = String(event.event_type);
                    const borderColor =
                      evtStr.includes("talk") || evtStr.includes("speech") || evtStr.includes("conversation")
                        ? "border-l-blue-300 bg-blue-50/30"
                        : evtStr.includes("rejected")
                          ? "border-l-red-300 bg-red-50/30"
                          : "border-l-emerald-200 bg-emerald-50/20";
                    return (
                      <div
                        key={event.id}
                        className={`flex items-start gap-2 rounded-r-lg border-l-2 py-1.5 pl-2.5 pr-2 ${borderColor}`}
                      >
                        <div className="min-w-0 flex-1">
                          <p className="text-xs leading-tight text-slate-700">{describeAgentEvent(event)}</p>
                          {event.location_name && (
                            <p className="mt-0.5 text-[10px] text-slate-400">📍 {event.location_name}</p>
                          )}
                        </div>
                        {timeLabel && (
                          <span className="shrink-0 text-[10px] text-slate-400">{timeLabel}</span>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </section>

          {/* 记忆 */}
          <section className="flex min-h-0 flex-1 flex-col rounded-2xl border border-slate-200 bg-white p-4 shadow-xs">
            <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-700">
              <span className="h-4 w-1 rounded-full bg-amber-500" />
              内部记忆栈
              <span className="ml-1 text-xs font-normal text-slate-400">({memories.length})</span>
            </h3>
            <div className="flex-1 overflow-y-auto pr-1">
            {memories.length === 0 ? (
              <p className="text-sm text-slate-400">暂无记忆数据</p>
            ) : (
              <div className="space-y-2">
                {memories.slice(0, 20).map((memory) => {
                  const importanceScore = formatAgentScore(memory.importance);
                  const isLowImportance = memory.importance != null && memory.importance < 0.3;
                  const tooltipText = `事件显著性: ${formatAgentScore(memory.event_importance)} | 主体相关性: ${formatAgentScore(memory.self_relevance)}`;
                  return (
                    <div
                      key={memory.id}
                      className={`rounded-xl border border-slate-100 p-3 ${isLowImportance ? "bg-slate-50/30 opacity-60" : "bg-slate-50/50"}`}
                    >
                      <div className="mb-1.5 flex items-center justify-between gap-2">
                        <div className="flex items-center gap-1.5">
                          <span
                            className={`rounded-full border px-2 py-0.5 text-[10px] ${memoryCategoryBadgeClass(memory.memory_category)}`}
                          >
                            {formatMemoryCategory(memory.memory_category)}
                          </span>
                          {(memory.streak_count ?? 1) > 1 && (
                            <span className="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[10px] text-slate-500">
                              ×{memory.streak_count}
                            </span>
                          )}
                        </div>
                        <div className="group relative flex items-center gap-1">
                          <span className={`text-[10px] font-medium ${memory.importance != null && memory.importance >= 0.7 ? "text-amber-600" : "text-slate-400"}`}>
                            ★ {importanceScore}
                          </span>
                          <div className="absolute right-0 top-5 z-10 hidden whitespace-nowrap rounded-lg bg-slate-800 px-2 py-1 text-[10px] text-white shadow-lg group-hover:block">
                            {tooltipText}
                          </div>
                        </div>
                      </div>
                      <p className="text-sm text-slate-700">{memory.content}</p>
                      {memory.created_at && (
                        <p className="mt-1 text-[10px] text-slate-400">
                          {formatRelativeTime(memory.created_at)}
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
            </div>
          </section>
        </div>
      </div>
    </Modal>
  );
}
