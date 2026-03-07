export type RunSummary = {
  id: string;
  name: string;
  status: string;
  current_tick?: number;
  tick_minutes?: number;
};

export type CreateRunResponse = {
  id: string;
  name: string;
  status: string;
};

export type TickResponse = {
  run_id: string;
  tick_no: number;
  accepted_count: number;
  rejected_count: number;
};

export type TimelineEvent = {
  id: string;
  tick_no: number;
  event_type: string;
  importance?: number;
  payload: Record<string, unknown>;
};

export type WorldSnapshot = {
  run: RunSummary;
  locations: Array<{
    id: string;
    name: string;
    location_type: string;
    x: number;
    y: number;
    capacity: number;
    occupants: AgentSummary[];
  }>;
  recent_events: Array<{
    id: string;
    tick_no: number;
    event_type: string;
    location_id?: string;
    actor_agent_id?: string;
    target_agent_id?: string;
    payload: Record<string, unknown>;
  }>;
};

export type AgentDetails = {
  run_id: string;
  agent_id: string;
  name: string;
  occupation?: string;
  current_goal?: string;
  status?: Record<string, unknown>;
  recent_events: TimelineEvent[];
  memories: Array<{
    id: string;
    memory_type: string;
    summary?: string;
    content: string;
    importance?: number;
  }>;
  relationships: Array<{
    other_agent_id: string;
    familiarity: number;
    trust: number;
    affinity: number;
    relation_type: string;
  }>;
};

export type AgentSummary = {
  id: string;
  name: string;
  occupation?: string;
  current_goal?: string;
  current_location_id?: string;
};

const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000/api";

function resolveApiBaseUrl() {
  const publicBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "");
  const internalBaseUrl = process.env.INTERNAL_API_BASE_URL?.replace(/\/$/, "");

  if (typeof window === "undefined") {
    return internalBaseUrl ?? publicBaseUrl ?? DEFAULT_API_BASE_URL;
  }

  return publicBaseUrl ?? DEFAULT_API_BASE_URL;
}

async function safeFetch<T>(path: string, fallback: T): Promise<T> {
  try {
    const response = await fetch(`${resolveApiBaseUrl()}${path}`, {
      cache: "no-store",
      headers: {
        Accept: "application/json",
      },
    });

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
    const response = await fetch(`${resolveApiBaseUrl()}${path}`, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });

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

export async function createRun(name: string, seedDemo = true): Promise<CreateRunResponse | null> {
  return safePost<CreateRunResponse | null>("/runs", { name, seed_demo: seedDemo }, null);
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
    const response = await fetch(`${resolveApiBaseUrl()}${path}`, {
      method: "DELETE",
      headers: {
        Accept: "application/json",
      },
    });

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
