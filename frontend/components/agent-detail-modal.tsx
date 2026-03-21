"use client";

import { useEffect, useState } from "react";
import { Modal } from "@/components/modal";
import { AgentAvatar } from "@/components/agent-avatar";
import { AgentSignalsPanel } from "@/components/agent-signals-panel";
import {
  inferAgentStatus,
  relationshipTone,
} from "@/lib/agent-utils";
import { getAgentResult } from "@/lib/api";
import { useWorld } from "@/components/world-context";
import type { AgentDetails, AgentRelationship } from "@/lib/types";

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

// 只展示有意义的角色配置字段（过滤 UUID / 路径等技术字段）
const PROFILE_SHOW: Array<{ key: string; label: string }> = [
  { key: "bio", label: "简介" },
  { key: "world_role", label: "世界角色" },
  { key: "occupation", label: "职业" },
  { key: "work_description", label: "工作描述" },
  { key: "work_schedule", label: "工作时间" },
];

// 状态样式
const STATUS_STYLE: Record<string, { badge: string; label: string }> = {
  talking:  { badge: "bg-sky-100 text-sky-700 border-sky-200",     label: "对话中" },
  working:  { badge: "bg-emerald-100 text-emerald-700 border-emerald-200", label: "工作中" },
  resting:  { badge: "bg-slate-100 text-slate-500 border-slate-200",  label: "休息中" },
  moving:   { badge: "bg-amber-100 text-amber-700 border-amber-200",  label: "移动中" },
  idle:     { badge: "bg-slate-50 text-slate-400 border-slate-100",   label: "空闲" },
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
        if (agentRes.data) { setAgent(agentRes.data); return; }
        setError(agentRes.error === "network_error" ? "网络错误" : "未找到智能体");
      })
      .catch(() => setError("加载失败"))
      .finally(() => setLoading(false));
  }, [isOpen, runId, agentId]);

  if (loading) {
    return (
      <Modal isOpen={isOpen} onClose={onClose} variant="inspector" showCloseButton>
        <div className="flex h-64 items-center justify-center text-slate-400">
          <div className="mr-2 h-5 w-5 animate-spin rounded-full border-2 border-slate-200 border-t-moss" />
          加载中...
        </div>
      </Modal>
    );
  }

  if (error || !agent) {
    return (
      <Modal isOpen={isOpen} onClose={onClose} variant="panel" showCloseButton>
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
  const { badge: statusBadge, label: statusLabel } = STATUS_STYLE[status] ?? STATUS_STYLE.idle;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      variant="inspector"
      showCloseButton
      // 规范：标题直接显示 agent 名字，副标题显示职业，不重复弹窗外已有信息
      title={agent.name}
      subtitle={agent.occupation || "居民"}
    >
      <div className="flex min-h-0 flex-1 overflow-hidden">
        {/* ── 左侧：身份档案 ── */}
        <aside className="flex w-72 shrink-0 flex-col border-r border-slate-100 bg-slate-50/60">
          <div className="flex-1 space-y-3 overflow-y-auto p-4">

            {/* 头像 + 状态 badge + 目标 */}
            <section className="rounded-2xl border border-white/70 bg-white p-4 shadow-xs">
              <div className="flex items-start gap-3">
                <AgentAvatar
                  agentId={agent.agent_id}
                  name={agent.name}
                  occupation={agent.occupation}
                  status={status}
                  size="lg"
                  configId={agent.config_id}
                />
                <div className="min-w-0 pt-0.5">
                  <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-medium ${statusBadge}`}>
                    {statusLabel}
                  </span>
                  {agent.current_goal && (
                    <p className="mt-2 line-clamp-3 text-[11px] leading-relaxed text-slate-500">
                      🎯 {agent.current_goal}
                    </p>
                  )}
                </div>
              </div>
            </section>

            {/* 人格特质 */}
            {Object.keys(personality).length > 0 && (
              <section className="rounded-2xl border border-white/70 bg-white p-4 shadow-xs">
                <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-moss">人格</p>
                <div className="mt-3 space-y-2.5">
                  {Object.entries(personality).map(([key, value]) => (
                    <div key={key} className="flex items-center gap-2">
                      <span className="w-14 shrink-0 text-[11px] text-slate-500">
                        {PERSONALITY_LABELS[key] || key}
                      </span>
                      <div className="h-[5px] flex-1 overflow-hidden rounded-full bg-slate-100">
                        <div
                          className="h-full rounded-full bg-moss"
                          style={{ width: `${(value as number) * 100}%` }}
                        />
                      </div>
                      <span className="w-7 shrink-0 text-right text-[10px] tabular-nums text-slate-400">
                        {(value as number).toFixed(1)}
                      </span>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* 角色设定（只展示有意义字段） */}
            {PROFILE_SHOW.some(({ key }) => profile[key] != null && String(profile[key]).trim()) && (
              <section className="rounded-2xl border border-white/70 bg-white p-4 shadow-xs">
                <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-moss">角色设定</p>
                <div className="mt-3 space-y-2.5">
                  {PROFILE_SHOW.filter(({ key }) => profile[key] != null && String(profile[key]).trim()).map(({ key, label }) => (
                    <div key={key}>
                      <p className="text-[10px] text-slate-400">{label}</p>
                      <p className="mt-0.5 text-xs leading-relaxed text-slate-700">{String(profile[key])}</p>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* 关系网络 */}
            {relationships.length > 0 && (
              <section className="rounded-2xl border border-white/70 bg-white p-4 shadow-xs">
                <div className="flex items-center justify-between">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-moss">关系网络</p>
                  <span className="text-[10px] text-slate-400">{relationships.length} 人</span>
                </div>
                <div className="mt-3 space-y-2.5">
                  {(showAllRelationships ? relationships : relationships.slice(0, 5)).map((rel: AgentRelationship, index: number) => {
                    const pct = rel.familiarity * 100;
                    const barColor = relationshipTone(rel.familiarity);
                    const valColor = rel.familiarity >= 0.75
                      ? "text-emerald-600"
                      : rel.familiarity >= 0.45 ? "text-amber-600" : "text-slate-400";
                    return (
                      <div key={`${rel.other_agent_id}-${index}`} className="flex items-center gap-2">
                        <span className="w-16 shrink-0 truncate text-[11px] text-slate-600">
                          {rel.other_agent_name || "未知"}
                        </span>
                        <div className="h-[5px] flex-1 overflow-hidden rounded-full bg-slate-100">
                          <div className={`h-full rounded-full ${barColor}`} style={{ width: `${pct.toFixed(0)}%` }} />
                        </div>
                        <span className={`w-8 shrink-0 text-right text-[10px] tabular-nums ${valColor}`}>
                          {pct.toFixed(0)}%
                        </span>
                      </div>
                    );
                  })}
                </div>
                {relationships.length > 5 && (
                  <button
                    type="button"
                    onClick={() => setShowAllRelationships((v) => !v)}
                    className="mt-3 w-full rounded-lg py-1 text-[11px] text-slate-400 transition hover:text-slate-600"
                  >
                    {showAllRelationships ? "收起" : `还有 ${relationships.length - 5} 个 ▾`}
                  </button>
                )}
              </section>
            )}
          </div>
        </aside>

        {/* ── 右侧：行为流 + 记忆 ── */}
        <div className="flex min-h-0 flex-1 overflow-hidden bg-slate-50/30 p-4">
          <AgentSignalsPanel agent={agent} world={world} compact />
        </div>
      </div>
    </Modal>
  );
}
