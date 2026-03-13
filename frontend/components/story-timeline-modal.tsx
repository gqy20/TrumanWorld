"use client";

import { useState, useMemo } from "react";
import type { StoryChapter, StoryEvent } from "@/lib/world-insights";
import { Modal, WorkspaceModalShell } from "@/components/modal";

interface StoryTimelineModalProps {
  isOpen: boolean;
  onClose: () => void;
  chapters: StoryChapter[];
}

export function StoryTimelineModal({ isOpen, onClose, chapters }: StoryTimelineModalProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<string | null>(null);
  const [selectedEventType, setSelectedEventType] = useState<string | null>(null);

  // 统计信息
  const stats = useMemo(() => {
    const allEvents = chapters.flatMap((c) => c.events);
    return {
      totalEvents: allEvents.length,
      talkCount: allEvents.filter((e) => e.type === "social").length,
      moveCount: allEvents.filter((e) => e.type === "move").length,
      rejectionCount: allEvents.filter((e) => e.type === "rejection").length,
    };
  }, [chapters]);

  // 过滤章节
  const filteredChapters = useMemo(() => {
    return chapters.filter((chapter) => {
      if (selectedPeriod && chapter.period !== selectedPeriod) return false;
      if (selectedEventType) {
        return chapter.events.some((e) => e.type === selectedEventType);
      }
      return true;
    });
  }, [chapters, selectedPeriod, selectedEventType]);

  if (!isOpen) return null;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      variant="workspace"
      title="📖 完整故事时间线"
      subtitle={`共 ${stats.totalEvents} 个事件 · ${chapters.length} 个时段`}
    >
      <WorkspaceModalShell
        toolbar={
          <div className="flex items-center gap-4">
            <StatBadge
              icon="💬"
              label="社交"
              count={stats.talkCount}
              isActive={selectedEventType === "social"}
              onClick={() => setSelectedEventType(selectedEventType === "social" ? null : "social")}
            />
            <StatBadge
              icon="🚶"
              label="移动"
              count={stats.moveCount}
              isActive={selectedEventType === "move"}
              onClick={() => setSelectedEventType(selectedEventType === "move" ? null : "move")}
            />
            <StatBadge
              icon="⚠️"
              label="异常"
              count={stats.rejectionCount}
              isActive={selectedEventType === "rejection"}
              onClick={() => setSelectedEventType(selectedEventType === "rejection" ? null : "rejection")}
            />
            {(selectedPeriod || selectedEventType) && (
              <button
                type="button"
                onClick={() => {
                  setSelectedPeriod(null);
                  setSelectedEventType(null);
                }}
                className="ml-auto text-xs text-slate-500 hover:text-moss"
              >
                清除筛选
              </button>
            )}
          </div>
        }
        contentClassName="overflow-auto px-6 py-4"
      >
        <div className="relative">
          <div className="absolute bottom-0 left-6 top-0 w-0.5 bg-slate-200" />
          <div className="space-y-6">
            {filteredChapters.map((chapter, index) => (
              <TimelineChapter
                key={chapter.id}
                chapter={chapter}
                isFirst={index === 0}
              />
            ))}
          </div>
        </div>
      </WorkspaceModalShell>
    </Modal>
  );
}

// 统计徽章
function StatBadge({
  icon,
  label,
  count,
  isActive,
  onClick,
}: {
  icon: string;
  label: string;
  count: number;
  isActive: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm transition ${
        isActive
          ? "bg-moss/10 text-moss ring-1 ring-moss/30"
          : "bg-white text-slate-600 hover:bg-slate-100"
      }`}
    >
      <span>{icon}</span>
      <span className="font-medium">{count}</span>
      <span className="text-xs text-slate-400">{label}</span>
    </button>
  );
}

// 时间线章节
function TimelineChapter({
  chapter,
  isFirst,
}: {
  chapter: StoryChapter;
  isFirst: boolean;
}) {
  return (
    <div className="relative pl-14">
      {/* 时间节点 */}
      <div
        className={`absolute left-0 flex h-12 w-12 flex-col items-center justify-center rounded-full border-2 ${
          isFirst
            ? "border-moss bg-moss/10 text-moss"
            : "border-slate-200 bg-white text-slate-500"
        }`}
      >
        <span className="text-lg">{chapter.periodIcon}</span>
      </div>

      {/* 章节内容 */}
      <div className="rounded-2xl border border-slate-100 bg-slate-50/50 p-4">
        <div className="mb-3 flex items-center justify-between">
          <div>
            <h3 className="font-medium text-ink">{chapter.periodName}</h3>
            <p className="text-xs text-slate-500">{chapter.timeLabel}</p>
          </div>
          <div className="flex gap-1">
            {chapter.highlights.slice(0, 2).map((h, i) => (
              <span
                key={i}
                className={`rounded-full px-2 py-0.5 text-xs ${
                  h.type === "warning"
                    ? "bg-amber-100 text-amber-700"
                    : h.type === "social"
                      ? "bg-rose-100 text-rose-700"
                      : "bg-slate-100 text-slate-600"
                }`}
              >
                {h.description}
              </span>
            ))}
          </div>
        </div>

        {/* 事件列表 */}
        <div className="space-y-2">
          {chapter.events.map((event) => (
            <TimelineEventItem key={event.id} event={event} />
          ))}
        </div>
      </div>
    </div>
  );
}

// 时间线事件项
function TimelineEventItem({ event }: { event: StoryEvent }) {
  const typeConfig = {
    move: { icon: "🚶", color: "text-blue-600", bg: "bg-blue-50" },
    social: { icon: "💬", color: "text-rose-600", bg: "bg-rose-50" },
    rejection: { icon: "⚠️", color: "text-amber-600", bg: "bg-amber-50" },
    work: { icon: "⚒️", color: "text-slate-600", bg: "bg-slate-50" },
    rest: { icon: "😴", color: "text-purple-600", bg: "bg-purple-50" },
    other: { icon: "•", color: "text-slate-500", bg: "bg-slate-50" },
  };
  const config = typeConfig[event.type];

  return (
    <div className="flex items-start gap-3 rounded-xl bg-white p-3 shadow-xs">
      <span className={`flex h-8 w-8 items-center justify-center rounded-lg ${config.bg} ${config.color}`}>
        {config.icon}
      </span>
      <div className="flex-1 min-w-0">
        <p className="text-sm text-ink">{event.description}</p>
        <div className="mt-1 flex items-center gap-2 text-xs text-slate-400">
          {event.locationName && <span>📍 {event.locationName}</span>}
          <span>· T{event.tickNo}</span>
        </div>
      </div>
    </div>
  );
}
