"use client";

import { useEffect, useRef } from "react";

import { buildApiUrl } from "@/lib/api";
import type { WorldEvent } from "@/lib/types";

type UseWorldEventStreamOptions = {
  enabled: boolean;
  latestKnownTick: number;
  onEvent: (event: WorldEvent) => void;
  runId: string;
};

export function useWorldEventStream({
  enabled,
  latestKnownTick,
  onEvent,
  runId,
}: UseWorldEventStreamOptions): void {
  const latestKnownTickRef = useRef(latestKnownTick);
  const runIdRef = useRef(runId);

  useEffect(() => {
    if (runIdRef.current !== runId) {
      runIdRef.current = runId;
      latestKnownTickRef.current = latestKnownTick;
      return;
    }
    latestKnownTickRef.current = Math.max(latestKnownTickRef.current, latestKnownTick);
  }, [latestKnownTick, runId]);

  useEffect(() => {
    if (!enabled || typeof EventSource === "undefined") return;
    const params = new URLSearchParams({
      since_tick: String(latestKnownTickRef.current),
    });
    const eventSource = new EventSource(
      buildApiUrl(`/runs/${runId}/events/stream?${params.toString()}`),
      { withCredentials: true },
    );
    const handleWorldEvent = (message: Event) => {
      const event = parseWorldEventMessage(message);
      if (!event) return;
      latestKnownTickRef.current = Math.max(latestKnownTickRef.current, event.tick_no);
      onEvent(event);
    };
    eventSource.addEventListener("world_event", handleWorldEvent);
    return () => {
      eventSource.removeEventListener("world_event", handleWorldEvent);
      eventSource.close();
    };
  }, [enabled, onEvent, runId]);
}

export function mergeWorldEvents(
  preferredEvents: WorldEvent[],
  fallbackEvents: WorldEvent[],
  limit = 60,
): WorldEvent[] {
  const merged: WorldEvent[] = [];
  const seenIds = new Set<string>();
  for (const event of [...preferredEvents, ...fallbackEvents]) {
    if (seenIds.has(event.id)) continue;
    seenIds.add(event.id);
    merged.push(event);
    if (merged.length >= limit) break;
  }
  return merged;
}

function parseWorldEventMessage(message: Event): WorldEvent | null {
  if (!(message instanceof MessageEvent) || typeof message.data !== "string") return null;
  try {
    const event = JSON.parse(message.data) as Partial<WorldEvent>;
    if (
      typeof event.id !== "string" ||
      typeof event.tick_no !== "number" ||
      typeof event.event_type !== "string" ||
      !event.payload ||
      typeof event.payload !== "object"
    ) {
      return null;
    }
    return event as WorldEvent;
  } catch {
    return null;
  }
}
