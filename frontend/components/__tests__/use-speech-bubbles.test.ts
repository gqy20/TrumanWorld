import { act, renderHook } from "@testing-library/react";

import type { WorldEvent } from "@/lib/types";

import { useSpeechBubbles } from "../use-speech-bubbles";

function speechEvent(id: string, agentId: string, message: string): WorldEvent {
  return {
    id,
    tick_no: 1,
    event_type: "speech",
    actor_agent_id: agentId,
    payload: { message },
  };
}

describe("useSpeechBubbles", () => {
  beforeEach(() => {
    jest.useFakeTimers();
    jest.setSystemTime(new Date("2026-05-16T00:00:00Z"));
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it("creates a bubble for a speech event and expires it after the ttl", () => {
    const { result } = renderHook(({ events }) => useSpeechBubbles(events), {
      initialProps: { events: [speechEvent("event-1", "agent-1", "hello")] },
    });

    expect(result.current["agent-1"]).toMatchObject({ message: "hello" });

    act(() => {
      jest.advanceTimersByTime(6000);
    });

    expect(result.current["agent-1"]).toBeUndefined();
  });

  it("does not recreate a bubble when the same event id is rendered again", () => {
    const events = [speechEvent("event-1", "agent-1", "hello")];
    const { result, rerender } = renderHook(({ currentEvents }) => useSpeechBubbles(currentEvents), {
      initialProps: { currentEvents: events },
    });
    const initialKey = result.current["agent-1"].key;

    jest.setSystemTime(new Date("2026-05-16T00:00:01Z"));
    rerender({ currentEvents: events });

    expect(result.current["agent-1"].key).toBe(initialKey);
  });

  it("keeps only the four most recent agent bubbles", () => {
    const events = [
      speechEvent("event-1", "agent-1", "one"),
      speechEvent("event-2", "agent-2", "two"),
      speechEvent("event-3", "agent-3", "three"),
      speechEvent("event-4", "agent-4", "four"),
      speechEvent("event-5", "agent-5", "five"),
    ];

    const { result } = renderHook(({ currentEvents }) => useSpeechBubbles(currentEvents), {
      initialProps: { currentEvents: events },
    });

    expect(Object.keys(result.current)).toHaveLength(4);
    expect(result.current["agent-1"]).toBeUndefined();
    expect(result.current["agent-5"]).toMatchObject({ message: "five" });
  });

  it("ignores talk and speech events without a string message", () => {
    const { result } = renderHook(({ events }) => useSpeechBubbles(events), {
      initialProps: {
        events: [
          { ...speechEvent("event-1", "agent-1", "hello"), payload: {} },
          { ...speechEvent("event-2", "agent-2", "hello"), payload: { message: 42 } },
        ],
      },
    });

    expect(result.current).toEqual({});
  });
});
