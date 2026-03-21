"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import useSWR from "swr";
import { buildApiUrl, fetchApiResult, getWorldPulseResult, type ApiResult } from "@/lib/api";
import type { WorldPulse, WorldSnapshot } from "@/lib/types";
import { useUiSearchParams } from "@/lib/ui-url-state";

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

// Deep equality check for world data to prevent unnecessary re-renders
function isWorldDataEqual(a: WorldSnapshot | null, b: WorldSnapshot | null): boolean {
  if (a === b) return true;
  if (!a || !b) return false;

  // Compare key fields that affect rendering
  if (a.run.current_tick !== b.run.current_tick) return false;
  if (a.run.status !== b.run.status) return false;
  if (a.locations.length !== b.locations.length) return false;
  if (a.recent_events.length !== b.recent_events.length) return false;

  // Compare location occupant counts (main visual change)
  for (let i = 0; i < a.locations.length; i++) {
    const aOccupants = a.locations[i].occupants ?? [];
    const bOccupants = b.locations[i].occupants ?? [];
    if (aOccupants.length !== bOccupants.length) {
      return false;
    }
  }

  return true;
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
        pausePolling ? 0 : snapshot?.data?.run.status === "running" ? 15000 : 0,
      revalidateOnFocus: false,
      revalidateOnMount: true,
      // Keep previous data during revalidation to prevent full-screen flash
      keepPreviousData: true,
      // Use compare function to prevent re-renders when data hasn't meaningfully changed
      compare: (a, b) => {
        if (!a?.data && !b?.data) return true;
        return isWorldDataEqual(a?.data ?? null, b?.data ?? null);
      },
    },
  );

  const { data: pulseResult } = useSWR<ApiResult<WorldPulse>>(
    isClient && !pausePolling ? `/runs/${runId}/world/pulse` : null,
    () => getWorldPulseResult(runId),
    {
      refreshInterval: (snapshot) =>
        snapshot?.data?.run.status === "running" ? 5000 : 0,
      revalidateOnFocus: false,
      revalidateOnMount: false,
      keepPreviousData: true,
    },
  );

  const refresh = useCallback(() => {
    void mutate();
  }, [mutate]);

  const error = result?.error ?? null;
  const world = result?.data ?? initialData ?? null;
  const pulse = pulseResult?.data ?? null;

  return (
    <WorldContext.Provider value={{ runId, world: world ?? null, pulse, error, isValidating, refresh }}>
      {children}
    </WorldContext.Provider>
  );
}
