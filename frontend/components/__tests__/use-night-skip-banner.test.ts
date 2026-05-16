import { act, renderHook } from "@testing-library/react";

import type { WorldClock } from "@/lib/types";

import { useNightSkipBanner } from "../use-night-skip-banner";

function clock(day: number, hour: number): WorldClock {
  return {
    iso: `2026-05-${String(day).padStart(2, "0")}T${String(hour).padStart(2, "0")}:00:00Z`,
    date: `2026-05-${String(day).padStart(2, "0")}`,
    time: `${String(hour).padStart(2, "0")}:00`,
    year: 2026,
    month: 5,
    day,
    hour,
    minute: 0,
    weekday: 1,
    weekday_name: "Monday",
    weekday_name_cn: "周一",
    is_weekend: false,
    time_period: "morning",
    time_period_cn: "早晨",
  };
}

describe("useNightSkipBanner", () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it("shows the banner when the clock advances from night to next morning", () => {
    const { result, rerender } = renderHook(({ worldClock }) => useNightSkipBanner(worldClock), {
      initialProps: { worldClock: clock(1, 22) },
    });

    expect(result.current.showNightSkip).toBe(false);

    rerender({ worldClock: clock(2, 7) });

    expect(result.current).toEqual({ showNightSkip: true, nightSkipDay: 2 });

    act(() => {
      jest.advanceTimersByTime(4500);
    });

    expect(result.current.showNightSkip).toBe(false);
  });

  it("does not show the banner for normal same-day hour changes", () => {
    const { result, rerender } = renderHook(({ worldClock }) => useNightSkipBanner(worldClock), {
      initialProps: { worldClock: clock(1, 8) },
    });

    rerender({ worldClock: clock(1, 9) });

    expect(result.current.showNightSkip).toBe(false);
    expect(result.current.nightSkipDay).toBe(1);
  });
});
