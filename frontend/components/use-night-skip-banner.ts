"use client";

import { useEffect, useRef, useState } from "react";

import type { WorldClock } from "@/lib/types";

const NIGHT_SKIP_BANNER_MS = 4500;

export function useNightSkipBanner(worldClock?: WorldClock) {
  const [showNightSkip, setShowNightSkip] = useState(false);
  const [nightSkipDay, setNightSkipDay] = useState(1);
  const prevClockRef = useRef<{ hour: number; day: number } | null>(null);

  useEffect(() => {
    if (!worldClock) {
      return;
    }

    const prev = prevClockRef.current;
    if (prev !== null && prev.hour >= 21 && worldClock.hour <= 7 && worldClock.day > prev.day) {
      setNightSkipDay(worldClock.day);
      setShowNightSkip(true);
      const timer = setTimeout(() => setShowNightSkip(false), NIGHT_SKIP_BANNER_MS);
      prevClockRef.current = { hour: worldClock.hour, day: worldClock.day };
      return () => clearTimeout(timer);
    }

    prevClockRef.current = { hour: worldClock.hour, day: worldClock.day };
  }, [worldClock]);

  return { showNightSkip, nightSkipDay };
}
