"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { motion, AnimatePresence } from "framer-motion";
import { useWorld } from "@/components/world-context";

interface SleepTransitionAnimationProps {
  /** 触发动画的最小天数差（默认 1） */
  minDayDiff?: number;
}

type AnimationState = "idle" | "fading-out" | "showing-text" | "fading-in";

// 预定义星星位置（避免在渲染时调用 Math.random）
const STAR_POSITIONS = [
  { left: 15, top: 12 },
  { left: 45, top: 8 },
  { left: 78, top: 25 },
  { left: 22, top: 35 },
  { left: 65, top: 18 },
  { left: 88, top: 42 },
  { left: 35, top: 52 },
  { left: 52, top: 28 },
  { left: 72, top: 48 },
  { left: 8, top: 22 },
  { left: 95, top: 38 },
  { left: 30, top: 15 },
  { left: 60, top: 55 },
  { left: 42, top: 45 },
  { left: 18, top: 48 },
  { left: 82, top: 12 },
  { left: 55, top: 35 },
  { left: 25, top: 58 },
  { left: 70, top: 5 },
  { left: 48, top: 22 },
];

/**
 * 睡眠过渡动画组件
 *
 * 检测时间从深夜跳到清晨（跨天）时，显示一个优雅的过渡动画：
 * 1. 淡出到深蓝色遮罩
 * 2. 显示 "🌙 夜晚过去了..." 文字
 * 3. 淡入显示新的早晨
 */
export function SleepTransitionAnimation({ minDayDiff = 1 }: SleepTransitionAnimationProps) {
  const { world, pulse } = useWorld();
  const [animationState, setAnimationState] = useState<AnimationState>("idle");
  const [newDay, setNewDay] = useState<number | null>(null);
  const [mounted, setMounted] = useState(false);

  // 记录上一次的天数
  const prevDayRef = useRef<number | null>(null);
  const prevHourRef = useRef<number | null>(null);

  // 计算当前模拟天数
  const currentWorldClock = pulse?.world_clock ?? world?.world_clock;
  const currentTick = pulse?.run?.current_tick ?? world?.run?.current_tick ?? 0;
  const tickMinutes = world?.run?.tick_minutes ?? 5;
  const currentDay = Math.floor((currentTick * tickMinutes) / 1440) + 1;
  const currentHour = currentWorldClock?.hour;

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    // 初始化时记录当前天数
    if (prevDayRef.current === null) {
      prevDayRef.current = currentDay;
      prevHourRef.current = currentHour ?? null;
      return;
    }

    const prevDay = prevDayRef.current;
    const prevHour = prevHourRef.current;

    // 检测跨天跳跃（天数增加 >= minDayDiff，且从晚上跳到早上）
    const dayDiff = currentDay - prevDay;
    const isNightToMorning =
      (prevHour !== null && prevHour >= 22) &&
      (currentHour !== undefined && currentHour >= 6 && currentHour < 12);

    if (dayDiff >= minDayDiff && isNightToMorning) {
      // 触发动画
      setNewDay(currentDay);
      setAnimationState("fading-out");

      // 阶段 1: 淡出 (0-800ms)
      setTimeout(() => {
        setAnimationState("showing-text");
      }, 800);

      // 阶段 2: 显示文字 (800-2500ms)
      setTimeout(() => {
        setAnimationState("fading-in");
      }, 2500);

      // 阶段 3: 淡入 (2500-3500ms)
      setTimeout(() => {
        setAnimationState("idle");
        setNewDay(null);
      }, 3500);
    }

    // 更新记录
    prevDayRef.current = currentDay;
    prevHourRef.current = currentHour ?? null;
  }, [currentDay, currentHour, minDayDiff]);

  // 使用 useMemo 稳定星星元素（虽然 STAR_POSITIONS 已经是静态的）
  const starElements = useMemo(
    () =>
      STAR_POSITIONS.map((pos, i) => (
        <motion.div
          key={i}
          initial={{ opacity: 0 }}
          animate={{ opacity: [0.3, 1, 0.3] }}
          transition={{
            duration: 2,
            repeat: Infinity,
            delay: i * 0.1,
          }}
          className="absolute h-1 w-1 rounded-full bg-white"
          style={{
            left: `${pos.left}%`,
            top: `${pos.top}%`,
          }}
        />
      )),
    [],
  );

  const isAnimating = animationState !== "idle";

  if (!mounted || !isAnimating) return null;

  const content = (
    <AnimatePresence>
      {isAnimating && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.8, ease: "easeInOut" }}
          className="fixed inset-0 z-9998 flex flex-col items-center justify-center"
          style={{
            background:
              animationState === "fading-out"
                ? "linear-gradient(to bottom, #0f172a, #1e293b)"
                : animationState === "showing-text"
                  ? "linear-gradient(to bottom, #1e293b, #334155)"
                  : "linear-gradient(to bottom, #334155, #64748b)",
          }}
        >
          {/* 星星背景 */}
          {animationState !== "fading-in" && (
            <div className="absolute inset-0 overflow-hidden">{starElements}</div>
          )}

          {/* 主图标 */}
          <motion.div
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{
              scale: animationState === "showing-text" ? 1.2 : 1,
              opacity: animationState === "fading-in" ? 0 : 1,
            }}
            transition={{ duration: 0.5 }}
            className="mb-6 text-6xl"
          >
            {animationState === "fading-out" ? "🌙" : animationState === "showing-text" ? "☀️" : "🌅"}
          </motion.div>

          {/* 文字 */}
          {(animationState === "showing-text" || animationState === "fading-in") && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: animationState === "fading-in" ? 0 : 1, y: 0 }}
              transition={{ duration: 0.5 }}
              className="text-center"
            >
              <p className="mb-2 text-xl font-medium text-white">夜晚过去了...</p>
              {newDay && <p className="text-sm text-slate-300">第 {newDay} 天的清晨</p>}
            </motion.div>
          )}

          {/* 底部渐变遮罩 */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: animationState === "fading-in" ? 0 : 1 }}
            className="absolute bottom-0 left-0 right-0 h-32 bg-gradient-to-t from-slate-900/80 to-transparent"
          />
        </motion.div>
      )}
    </AnimatePresence>
  );

  return createPortal(content, document.body);
}
