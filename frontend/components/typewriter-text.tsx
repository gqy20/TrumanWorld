"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";

interface TypewriterTextProps {
  text: string;
  speed?: number;
  onComplete?: () => void;
  isAnimating?: boolean;
  className?: string;
}

export function TypewriterText({
  text,
  speed = 30,
  onComplete,
  isAnimating = true,
  className = "",
}: TypewriterTextProps) {
  const [displayedChars, setDisplayedChars] = useState(0);

  // Reset when text changes
  useEffect(() => {
    setDisplayedChars(0);
  }, [text]);

  useEffect(() => {
    if (!isAnimating) {
      setDisplayedChars(text.length);
      return;
    }

    if (displayedChars >= text.length) {
      onComplete?.();
      return;
    }

    const timer = setTimeout(() => {
      setDisplayedChars((prev) => prev + 1);
    }, speed);

    return () => clearTimeout(timer);
  }, [displayedChars, text, speed, isAnimating, onComplete]);

  return (
    <span className={className}>
      {text.slice(0, displayedChars)}
      {displayedChars < text.length && (
        <motion.span
          animate={{ opacity: [1, 0] }}
          transition={{ duration: 0.5, repeat: Infinity }}
          className="ml-0.5 inline-block h-4 w-0.5 bg-current align-middle"
        />
      )}
    </span>
  );
}
