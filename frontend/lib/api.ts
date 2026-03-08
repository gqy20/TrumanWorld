import type {
  AgentDetails,
  AgentSummary,
  CreateRunResponse,
  RunSummary,
  TickResponse,
  TimelineEvent,
  WorldSnapshot,
} from "@/lib/types";

export type {
  AgentDetails,
  AgentSummary,
  CreateRunResponse,
  RunSummary,
  TickResponse,
  TimelineEvent,
  WorldClock,
  WorldEvent,
  WorldLocation,
  WorldSnapshot,
} from "@/lib/types";


const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000/api";

function resolveApiBaseUrl() {
  const publicBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "");
  const internalBaseUrl = process.env.INTERNAL_API_BASE_URL?.replace(/\/$/, "");

  if (typeof window === "undefined") {
    return internalBaseUrl ?? publicBaseUrl ?? DEFAULT_API_BASE_URL;
  }

  return publicBaseUrl ?? DEFAULT_API_BASE_URL;
}

export function getApiBaseUrl() {
  return resolveApiBaseUrl();
}

export function buildApiUrl(path: string) {
  return `${resolveApiBaseUrl()}${path}`;
}

async function safeFetch<T>(path: string, fallback: T): Promise<T> {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5000);

    const response = await fetch(buildApiUrl(path), {
      cache: "no-store",
      signal: controller.signal,
      headers: {
        Accept: "application/json",
      },
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      return fallback;
    }

    return (await response.json()) as T;
  } catch {
    return fallback;
  }
}

async function safePost<T>(path: string, body: unknown, fallback: T): Promise<T> {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000);

    const response = await fetch(buildApiUrl(path), {
      method: "POST",
      signal: controller.signal,
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      return fallback;
    }

    return (await response.json()) as T;
  } catch {
    return fallback;
  }
}

export async function getRun(runId: string): Promise<RunSummary | null> {
  return safeFetch<RunSummary | null>(`/runs/${runId}`, null);
}

export async function listRuns(): Promise<RunSummary[]> {
  return safeFetch<RunSummary[]>("/runs", []);
}

export async function getTimeline(runId: string): Promise<{ run_id: string; events: TimelineEvent[] }> {
  return safeFetch(`/runs/${runId}/timeline`, { run_id: runId, events: [] });
}

export async function getWorld(runId: string): Promise<WorldSnapshot | null> {
  return safeFetch<WorldSnapshot | null>(`/runs/${runId}/world`, null);
}

export async function getAgent(runId: string, agentId: string): Promise<AgentDetails | null> {
  return safeFetch<AgentDetails | null>(`/runs/${runId}/agents/${agentId}`, null);
}

export async function listAgents(runId: string): Promise<{ run_id: string; agents: AgentSummary[] }> {
  return safeFetch(`/runs/${runId}/agents`, { run_id: runId, agents: [] });
}

export async function createRun(
  name: string,
  scenarioType = "truman_world",
  seedDemo = true,
  tickMinutes = 5,
): Promise<CreateRunResponse | null> {
  return safePost<CreateRunResponse | null>(
    "/runs",
    {
      name,
      scenario_type: scenarioType,
      seed_demo: seedDemo,
      tick_minutes: tickMinutes,
    },
    null,
  );
}

export async function startRun(runId: string): Promise<RunSummary | null> {
  return safePost<RunSummary | null>(`/runs/${runId}/start`, {}, null);
}

export async function pauseRun(runId: string): Promise<RunSummary | null> {
  return safePost<RunSummary | null>(`/runs/${runId}/pause`, {}, null);
}

export async function resumeRun(runId: string): Promise<RunSummary | null> {
  return safePost<RunSummary | null>(`/runs/${runId}/resume`, {}, null);
}

export async function advanceRunTick(runId: string): Promise<TickResponse | null> {
  return safePost<TickResponse | null>(`/runs/${runId}/tick`, {}, null);
}

export async function injectDirectorEvent(
  runId: string,
  input: {
    event_type: string;
    payload: Record<string, unknown>;
    location_id?: string;
    importance?: number;
  },
): Promise<{ run_id: string; status: string } | null> {
  return safePost<{ run_id: string; status: string } | null>(`/runs/${runId}/director/events`, input, null);
}

async function safeDelete<T>(path: string, fallback: T): Promise<T> {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5000);

    const response = await fetch(buildApiUrl(path), {
      method: "DELETE",
      signal: controller.signal,
      headers: {
        Accept: "application/json",
      },
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      return fallback;
    }

    return (await response.json()) as T;
  } catch {
    return fallback;
  }
}

export async function deleteRun(runId: string): Promise<{ run_id: string; status: string } | null> {
  return safeDelete<{ run_id: string; status: string } | null>(`/runs/${runId}`, null);
}

export async function restoreAllRuns(): Promise<RunSummary[]> {
  return safePost<RunSummary[]>('/runs/restore-all', {}, []);
}

export async function fetchApiOrThrow<T>(url: string): Promise<T> {
  const response = await fetch(url, {
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export async function fetchApiOrFallback<T>(url: string, fallback: T): Promise<T> {
  try {
    const response = await fetch(url, {
      headers: {
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      return fallback;
    }

    return response.json() as Promise<T>;
  } catch {
    return fallback;
  }
}
