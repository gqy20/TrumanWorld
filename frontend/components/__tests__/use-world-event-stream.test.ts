import { act, renderHook } from "@testing-library/react";

import type { WorldEvent } from "@/lib/types";

import { mergeWorldEvents, useWorldEventStream } from "../use-world-event-stream";

class MockEventSource {
  static instances: MockEventSource[] = [];

  readonly url: string;
  readonly withCredentials: boolean;
  closed = false;
  private listeners = new Map<string, Set<EventListener>>();

  constructor(url: string | URL, options?: EventSourceInit) {
    this.url = String(url);
    this.withCredentials = options?.withCredentials ?? false;
    MockEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: EventListenerOrEventListenerObject): void {
    if (typeof listener !== "function") return;
    const listeners = this.listeners.get(type) ?? new Set<EventListener>();
    listeners.add(listener);
    this.listeners.set(type, listeners);
  }

  removeEventListener(type: string, listener: EventListenerOrEventListenerObject): void {
    if (typeof listener === "function") this.listeners.get(type)?.delete(listener);
  }

  close(): void {
    this.closed = true;
  }

  emit(type: string, data: string): void {
    const event = new MessageEvent(type, { data });
    this.listeners.get(type)?.forEach((listener) => listener(event));
  }
}

function worldEvent(id: string, tick: number): WorldEvent {
  return {
    id,
    tick_no: tick,
    event_type: "move",
    payload: { from_location_id: "library", to_location_id: "cafe" },
  };
}

describe("useWorldEventStream", () => {
  const NativeEventSource = global.EventSource;

  beforeEach(() => {
    MockEventSource.instances = [];
    global.EventSource = MockEventSource as unknown as typeof EventSource;
  });

  afterEach(() => {
    global.EventSource = NativeEventSource;
  });

  it("opens a credentialed incremental stream and closes it on unmount", () => {
    const onEvent = jest.fn();
    const { unmount } = renderHook(() =>
      useWorldEventStream({ enabled: true, latestKnownTick: 24, onEvent, runId: "run-1" }),
    );
    const source = MockEventSource.instances[0];

    expect(source.url).toContain("/runs/run-1/events/stream?since_tick=24");
    expect(source.withCredentials).toBe(true);

    act(() => source.emit("world_event", JSON.stringify(worldEvent("event-25", 25))));
    expect(onEvent).toHaveBeenCalledWith(worldEvent("event-25", 25));

    act(() => source.emit("world_event", "not-json"));
    expect(onEvent).toHaveBeenCalledTimes(1);

    unmount();
    expect(source.closed).toBe(true);
  });
});

describe("mergeWorldEvents", () => {
  it("keeps streamed events first, removes duplicates, and respects the limit", () => {
    expect(
      mergeWorldEvents(
        [worldEvent("event-3", 3), worldEvent("event-2", 2)],
        [worldEvent("event-2", 2), worldEvent("event-1", 1)],
        2,
      ).map((event) => event.id),
    ).toEqual(["event-3", "event-2"]);
  });
});
