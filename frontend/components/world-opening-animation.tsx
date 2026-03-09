"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import Image from "next/image";

interface WorldOpeningAnimationProps {
  isVisible: boolean;
  onComplete: () => void;
  runName?: string;
}

type Stage = "noise" | "zoom" | "text" | "fade" | "done";

export function WorldOpeningAnimation({ isVisible, onComplete, runName }: WorldOpeningAnimationProps) {
  const [stage, setStage] = useState<Stage>("done");

  useEffect(() => {
    if (!isVisible) {
      setStage("done");
      return;
    }

    // 阶段 1: 雪花噪点 (0-1s)
    setStage("noise");

    // 阶段 2: 镜头拉近 (1-2s)
    const zoomTimer = setTimeout(() => setStage("zoom"), 1000);

    // 阶段 3: 打字机文字 (2-4s)
    const textTimer = setTimeout(() => setStage("text"), 2000);

    // 阶段 4: 渐出 (4-5s)
    const fadeTimer = setTimeout(() => setStage("fade"), 4000);

    // 完成
    const completeTimer = setTimeout(() => {
      setStage("done");
      onComplete();
    }, 5000);

    return () => {
      clearTimeout(zoomTimer);
      clearTimeout(textTimer);
      clearTimeout(fadeTimer);
      clearTimeout(completeTimer);
    };
  }, [isVisible, onComplete]);

  // 跳过动画
  const handleSkip = () => {
    setStage("done");
    onComplete();
  };

  const isAnimating = stage !== "done";

  return (
    <AnimatePresence>
      {isAnimating && (
        <motion.div
          initial={{ opacity: 1 }}
          animate={{ opacity: isAnimating ? 1 : 0 }}
          transition={{ duration: 0.5 }}
          className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-black"
          onClick={handleSkip}
        >
          {/* 阶段 1: 雪花噪点效果 */}
          {stage === "noise" && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI0IiBoZWlnaHQ9IjQiPgo8cmVjdCB3aWR0aD0iNCIgaGVpZ2h0PSI0IiBmaWxsPSIjZmZmIi8+CjxyZWN0IHdpZHRoPSIxIiBoZWlnaHQ9IjEiIGZpbGw9IiMyMjIiIG9wYWNpdHk9IjAuNCIvPgo8L3N2Zz4=')] bg-[length:4px_4px]"
            />
          )}

          {/* 阶段 2: 镜头拉近到小镇 */}
          {(stage === "zoom" || stage === "text" || stage === "fade") && (
            <motion.div
              initial={{ scale: 3, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ duration: 1, ease: "easeOut" }}
              className="relative h-64 w-64"
            >
              <Image
                src="/logo.svg"
                alt="Truman World"
                width={256}
                height={256}
                className="h-full w-full"
              />
            </motion.div>
          )}

          {/* 阶段 3: 打字机文字 */}
          {(stage === "text" || stage === "fade") && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.5 }}
              className="absolute bottom-32 text-center"
            >
              <TypewriterText
                text={runName ? `世界 "${runName}" 已创建` : "新世界已创建"}
                className="text-2xl font-medium text-white"
              />
              <motion.p
                initial={{ opacity: 0 }}
                animate={{ opacity: 0.5 }}
                transition={{ delay: 1.5 }}
                className="mt-4 text-sm text-slate-400"
              >
                点击任意位置跳过
              </motion.p>
            </motion.div>
          )}

          {/* 底部 logo */}
          {(stage === "text" || stage === "fade") && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.8 }}
              className="absolute bottom-8"
            >
              <p className="text-xs text-slate-500">Truman World</p>
            </motion.div>
          )}
        </motion.div>
      )}
    </AnimatePresence>
  );
}

// 简化版打字机组件（内联）
function TypewriterText({ text, className }: { text: string; className?: string }) {
  const [displayed, setDisplayed] = useState("");

  useEffect(() => {
    let i = 0;
    const timer = setInterval(() => {
      if (i < text.length) {
        setDisplayed(text.slice(0, i + 1));
        i++;
      } else {
        clearInterval(timer);
      }
    }, 80);
    return () => clearInterval(timer);
  }, [text]);

  return <span className={className}>{displayed}</span>;
}
