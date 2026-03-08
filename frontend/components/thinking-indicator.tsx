"use client";

import { motion } from "framer-motion";

interface ThinkingIndicatorProps {
  className?: string;
}

export function ThinkingIndicator({ className = "" }: ThinkingIndicatorProps) {
  return (
    <div className={`flex items-center gap-1 px-3 py-2 ${className}`}>
      {[0, 1, 2].map((i) => (
        <motion.span
          key={i}
          className="h-2 w-2 rounded-full bg-moss"
          animate={{
            y: [0, -6, 0],
            opacity: [0.4, 1, 0.4],
          }}
          transition={{
            duration: 0.8,
            repeat: Infinity,
            delay: i * 0.15,
          }}
        />
      ))}
    </div>
  );
}
