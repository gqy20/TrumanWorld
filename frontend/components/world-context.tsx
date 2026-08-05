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
import type { RunSummary, WorldEvent, WorldPulse, WorldSnapshot } from "@/lib/types";

import { mergeWorldEvents, useWorldEventStream } from "./use-world-event-stream";

type WorldContextValue = {
  runId: string;
  world: WorldSnapshot | null;
  pulse: WorldPulse | null;
  error: string | null;
  isValidating: boolean;
  updateRun: (run: RunSummary) => void;
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
      refreshInterval: (snapshot) => pollingInterval(snapshot, 15000),
      revalidateOnFocus: false,
      revalidateOnMount: initialData == null,
      // Keep previous data during revalidation to prevent full-screen flash
      keepPreviousData: true,
    },
  );

  const { data: pulseResult, mutate: mutatePulse } = useSWR<ApiResult<WorldPulse>>(
    isClient ? `/runs/${runId}/world/pulse` : null,
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
      if (streamRefreshTimerRef.current) clearTimeout(streamRefreshTimerRef.current);
      streamRefreshTimerRef.current = setTimeout(() => {
        void Promise.all([mutate(), mutatePulse()]);
        streamRefreshTimerRef.current = null;
      }, 120);
    },
    [mutate, mutatePulse],
  );

  useWorldEventStream({
    enabled: isClient && snapshot !== null,
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

  const updateRun = useCallback((run: RunSummary) => {
    void mutate(
      (current) => current?.data
        ? { ...current, data: { ...current.data, run } }
        : current,
      false,
    );
    void mutatePulse(
      (current) => current?.data
        ? { ...current, data: { ...current.data, run } }
        : current,
      false,
    );
    lastKnownRunStatus.current = run.status;
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
    <WorldContext.Provider
      value={{ runId, world: world ?? null, pulse, error, isValidating, updateRun, refresh }}
    >
      {children}
    </WorldContext.Provider>
  );
}
