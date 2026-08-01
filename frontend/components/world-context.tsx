"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import useSWR from "swr";
import { buildApiUrl, fetchApiResult, getWorldPulseResult, type ApiResult } from "@/lib/api";
import { EVENT_MOVE, EVENT_MOVE_ARRIVED } from "@/lib/simulation-protocol";
import type { WorldEvent, WorldPulse, WorldSnapshot } from "@/lib/types";
import { useUiSearchParams } from "@/lib/ui-url-state";

import { mergeWorldEvents, useWorldEventStream } from "./use-world-event-stream";

type WorldContextValue = {
  runId: string;
  world: WorldSnapshot | null;
  pulse: WorldPulse | null;
  error: string | null;
  isValidating: boolean;
  refresh: () => void;
};

const WorldContext = createContext<WorldContextValue | null>(null);

export function useWorld() {
  const context = useContext(WorldContext);
  if (!context) {
    throw new Error("useWorld must be used within a WorldProvider");
  }
  return context;
}

type Props = {
  runId: string;
  initialData?: WorldSnapshot | null;
  children: ReactNode;
};

export function WorldProvider({ runId, initialData, children }: Props) {
  const [isClient, setIsClient] = useState(false);
  const { searchParams } = useUiSearchParams();
  const activeModal = searchParams.get("modal");
  const pausePolling = activeModal !== null;
  const lastKnownRunStatus = useRef(initialData?.run.status ?? null);
  const [streamedEvents, setStreamedEvents] = useState<WorldEvent[]>([]);
  const streamRefreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const pollingInterval = useCallback(
    (
      snapshot: ApiResult<WorldSnapshot | WorldPulse> | undefined,
      intervalMs: number,
    ) => {
      const currentStatus = snapshot?.data?.run.status;
      if (currentStatus) {
        lastKnownRunStatus.current = currentStatus;
      }
      return (currentStatus ?? lastKnownRunStatus.current) === "running" ? intervalMs : 0;
    },
    [],
  );

  useEffect(() => {
    setIsClient(true);
  }, []);

  const { data: result, isValidating, mutate } = useSWR<ApiResult<WorldSnapshot>>(
    isClient ? buildApiUrl(`/runs/${runId}/world`) : null,
    fetchApiResult,
    {
      fallbackData: {
        data: initialData ?? null,
        error: null,
        errorCode: null,
        errorDetail: null,
        status: initialData ? 200 : null,
      },
      refreshInterval: (snapshot) =>
        pausePolling ? 0 : pollingInterval(snapshot, 15000),
      revalidateOnFocus: false,
      revalidateOnMount: true,
      // Keep previous data during revalidation to prevent full-screen flash
      keepPreviousData: true,
    },
  );

  const { data: pulseResult, mutate: mutatePulse } = useSWR<ApiResult<WorldPulse>>(
    isClient && !pausePolling ? `/runs/${runId}/world/pulse` : null,
    () => getWorldPulseResult(runId),
    {
      refreshInterval: (snapshot) => pollingInterval(snapshot, 5000),
      revalidateOnFocus: false,
      revalidateOnMount: true,
      keepPreviousData: true,
    },
  );

  const snapshot = result?.data ?? initialData ?? null;
  const latestKnownTick = Math.max(
    snapshot?.run.current_tick ?? 0,
    ...streamedEvents.map((event) => event.tick_no),
  );
  const handleStreamEvent = useCallback(
    (event: WorldEvent) => {
      setStreamedEvents((current) => mergeWorldEvents([event], current));
      if (event.event_type !== EVENT_MOVE && event.event_type !== EVENT_MOVE_ARRIVED) return;
      if (streamRefreshTimerRef.current) clearTimeout(streamRefreshTimerRef.current);
      streamRefreshTimerRef.current = setTimeout(() => {
        void mutate();
        streamRefreshTimerRef.current = null;
      }, 120);
    },
    [mutate],
  );

  useWorldEventStream({
    enabled: isClient && !pausePolling && snapshot !== null,
    latestKnownTick,
    onEvent: handleStreamEvent,
    runId,
  });

  useEffect(() => {
    setStreamedEvents([]);
  }, [runId]);

  useEffect(
    () => () => {
      if (streamRefreshTimerRef.current) clearTimeout(streamRefreshTimerRef.current);
    },
    [],
  );

  const refresh = useCallback(() => {
    void mutate();
    void mutatePulse();
  }, [mutate, mutatePulse]);

  const error = result?.error ?? null;
  const world = useMemo(
    () =>
      snapshot
        ? {
            ...snapshot,
            recent_events: mergeWorldEvents(streamedEvents, snapshot.recent_events),
          }
        : null,
    [snapshot, streamedEvents],
  );
  const pulse = pulseResult?.data ?? null;

  return (
    <WorldContext.Provider value={{ runId, world: world ?? null, pulse, error, isValidating, refresh }}>
      {children}
    </WorldContext.Provider>
  );
}
