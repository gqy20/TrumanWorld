"use client";

import { motion, AnimatePresence } from "framer-motion";
import { useState, useEffect } from "react";
import type { StoryChapter, StoryEvent } from "@/lib/world-insights";

interface StoryTimelineProps {
  chapters: StoryChapter[];
  onExpand?: () => void;
}

export function StoryTimeline({ chapters, onExpand }: StoryTimelineProps) {
  const [expandedChapters, setExpandedChapters] = useState<Set<string>>(new Set());

  // 当 chapters 数据变化时，默认展开第一个时段
  useEffect(() => {
    if (chapters.length > 0) {
      setExpandedChapters((prev) => {
        // 如果已经有展开的，保持现状；否则展开第一个
        if (prev.size > 0) return prev;
        return new Set([chapters[0].id]);
      });
    }
  }, [chapters]);

  const toggleChapter = (chapterId: string) => {
    setExpandedChapters((prev) => {
      const next = new Set(prev);
      if (next.has(chapterId)) {
        next.delete(chapterId);
      } else {
        next.add(chapterId);
      }
      return next;
    });
  };

  if (chapters.length === 0) {
    return (
      <div className="flex h-full flex-col rounded-[28px] border border-white/70 bg-white/80 p-4 shadow-xs backdrop-blur-sm">
        <h2 className="text-lg font-semibold text-ink">📖 今日故事线</h2>
        <p className="mt-4 text-sm text-slate-500">暂无故事数据</p>
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden rounded-[28px] border border-white/70 bg-white/80 p-4 shadow-xs backdrop-blur-sm">
      <div className="flex shrink-0 items-center justify-between">
        <h2 className="text-lg font-semibold text-ink">📖 今日故事线</h2>
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-400">{chapters.length} 个时段</span>
          {onExpand && (
            <button
              type="button"
              onClick={onExpand}
              className="flex h-7 w-7 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-400 shadow-xs transition hover:border-moss hover:text-moss"
              title="放大查看完整时间线"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-3.5 w-3.5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
              </svg>
            </button>
          )}
        </div>
      </div>

      <div className="mt-3 min-h-0 flex-1 space-y-2 overflow-y-auto pr-1">
        {chapters.map((chapter, index) => (
          <ChapterCard
            key={chapter.id}
            chapter={chapter}
            isExpanded={expandedChapters.has(chapter.id)}
            onToggle={() => toggleChapter(chapter.id)}
            isLatest={index === 0}
          />
        ))}
      </div>
    </div>
  );
}

// ============================================================================
// 章节卡片组件
// ============================================================================

interface ChapterCardProps {
  chapter: StoryChapter;
  isExpanded: boolean;
  onToggle: () => void;
  isLatest: boolean;
}

function ChapterCard({
  chapter,
  isExpanded,
  onToggle,
  isLatest,
}: ChapterCardProps) {
  return (
    <div
      className={`rounded-xl border transition-all ${
        isLatest
          ? "border-moss/30 bg-moss/5"
          : "border-slate-100 bg-slate-50/50"
      }`}
    >
      {/* 章节头部 - 压缩为单行 */}
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center justify-between p-2.5 text-left"
      >
        <div className="flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-100 text-lg">
            {chapter.periodIcon}
          </span>
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-ink">{chapter.periodName}</span>
            <span className="text-xs text-slate-400">{chapter.timeLabel}</span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* 亮点标签 - 更紧凑 */}
          <div className="hidden items-center gap-1 sm:flex">
            {chapter.highlights.slice(0, 2).map((highlight, idx) => (
              <CompactHighlightBadge key={idx} highlight={highlight} />
            ))}
          </div>

          {/* 展开/收起图标 */}
          <motion.svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            className="h-4 w-4 text-slate-400"
            animate={{ rotate: isExpanded ? 180 : 0 }}
            transition={{ duration: 0.2 }}
          >
            <path d="M19 9l-7 7-7-7" />
          </motion.svg>
        </div>
      </button>

      {/* 章节内容 */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="border-t border-slate-100 px-2.5 pb-2.5">
              {/* 事件列表 - 更紧凑 */}
              <div className="mt-2 space-y-1">
                {chapter.events.map((event) => (
                  <CompactEventItem key={event.id} event={event} />
                ))}
              </div>

              {/* 更多事件提示 - 简化 */}
              {chapter.events.length >= 5 && (
                <div className="mt-2 text-center">
                  <span className="text-[10px] text-slate-400">···</span>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ============================================================================
// 亮点标签组件（紧凑版）
// ============================================================================

interface CompactHighlightBadgeProps {
  highlight: {
    type: "normal" | "warning" | "social" | "work";
    description: string;
  };
}

function CompactHighlightBadge({ highlight }: CompactHighlightBadgeProps) {
  const typeClasses = {
    normal: "bg-slate-100 text-slate-500",
    warning: "bg-amber-100 text-amber-600",
    social: "bg-rose-100 text-rose-600",
    work: "bg-blue-100 text-blue-600",
  };

  const typeIcons = {
    normal: "•",
    warning: "⚠",
    social: "💬",
    work: "⚒",
  };

  // 提取数字
  const count = highlight.description.match(/\d+/)?.[0] || "";

  return (
    <span
      className={`inline-flex items-center gap-0.5 rounded-full px-1.5 py-0.5 text-[10px] ${typeClasses[highlight.type]}`}
    >
      <span>{typeIcons[highlight.type]}</span>
      <span>{count}</span>
    </span>
  );
}

// ============================================================================
// 事件项组件（紧凑版）
// ============================================================================

interface CompactEventItemProps {
  event: StoryEvent;
}

function CompactEventItem({ event }: CompactEventItemProps) {
  // 根据类型决定展示样式
  const isLowImportance = event.type === "work" || event.type === "rest";

  const typeClasses = {
    social: "border-l-rose-300 bg-rose-50/30",
    move: "border-l-emerald-300 bg-emerald-50/30",
    work: "border-l-slate-200 bg-slate-50/30",
    rest: "border-l-slate-200 bg-slate-50/30",
    rejection: "border-l-red-300 bg-red-50/30",
    other: "border-l-slate-200 bg-slate-50/30",
  };

  // 低重要性事件：单行展示
  if (isLowImportance) {
    return (
      <div className="flex items-center gap-2 rounded-r border-l-2 border-slate-200 py-1 pl-2 pr-2 text-xs text-slate-500">
        <span className="text-xs opacity-70">{event.icon}</span>
        <span className="truncate">{event.description}</span>
      </div>
    );
  }

  // 高重要性事件：保留一定视觉层次
  return (
    <div className={`flex items-start gap-2 rounded-r-lg border-l-2 py-1.5 pl-2.5 pr-2 ${typeClasses[event.type]}`}>
      <span className="text-sm">{event.icon}</span>
      <div className="min-w-0 flex-1">
        <p className="text-xs text-slate-700 leading-tight">{event.description}</p>
        {event.locationName && (
          <p className="mt-0.5 flex items-center gap-1 text-[10px] text-slate-400">
            <span className="inline-block h-1 w-1 rounded-full bg-slate-300" />
            {event.locationName}
          </p>
        )}
      </div>
      <span className="text-[10px] text-slate-400 shrink-0">{event.time}</span>
    </div>
  );
}

// ============================================================================
// 故事时间线预览（用于小空间展示）
// ============================================================================

interface StoryTimelineCompactProps {
  chapters: StoryChapter[];
  maxEvents?: number;
}

export function StoryTimelineCompact({
  chapters,
  maxEvents = 3,
}: StoryTimelineCompactProps) {
  const allEvents = chapters.flatMap((c) => c.events).slice(0, maxEvents);

  if (allEvents.length === 0) {
    return (
      <div className="rounded-xl border border-slate-100 bg-slate-50 p-3">
        <p className="text-sm text-slate-500">暂无故事数据</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-slate-100 bg-slate-50 p-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-slate-500">最新动态</span>
        <span className="text-xs text-slate-400">
          {chapters[0]?.periodIcon} {chapters[0]?.periodName}
        </span>
      </div>
      <div className="mt-2 space-y-2">
        {allEvents.map((event) => (
          <div key={event.id} className="flex items-center gap-2 text-sm">
            <span>{event.icon}</span>
            <span className="flex-1 truncate text-slate-700">
              {event.description}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
