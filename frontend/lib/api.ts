import type {
  AgentDetails,
  AgentSummary,
  CreateRunResponse,
  DirectorMemory,
  RunSummary,
  TickResponse,
  TimelineEvent,
  TimelineFilter,
  TimelineResponse,
  WorldEvent,
  WorldSnapshot,
} from "@/lib/types";

export type {
  AgentDetails,
  AgentSummary,
  CreateRunResponse,
  DirectorMemory,
  RunSummary,
  TickResponse,
  TimelineEvent,
  TimelineFilter,
  TimelineResponse,
  TimelineRunInfo,
  WorldClock,
  WorldEvent,
  WorldLocation,
  WorldSnapshot,
} from "@/lib/types";

export type ApiResult<T> = {
  data: T | null;
  error: string | null;
  status: number | null;
};


const DEFAULT_API_BASE_URL = "/api";

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

async function fetchResultUrl<T>(url: string): Promise<ApiResult<T>> {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5000);

    const response = await fetch(url, {
      cache: "no-store",
      signal: controller.signal,
      headers: {
        Accept: "application/json",
      },
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      return {
        data: null,
        error: response.status === 404 ? "not_found" : "request_failed",
        status: response.status,
      };
    }

    return {
      data: (await response.json()) as T,
      error: null,
      status: response.status,
    };
  } catch {
    return {
      data: null,
      error: "network_error",
      status: null,
    };
  }
}

async function fetchResult<T>(path: string): Promise<ApiResult<T>> {
  return fetchResultUrl<T>(buildApiUrl(path));
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

async function postResult<T>(path: string, body: unknown): Promise<ApiResult<T>> {
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
      return {
        data: null,
        error: response.status === 404 ? "not_found" : "request_failed",
        status: response.status,
      };
    }

    return {
      data: (await response.json()) as T,
      error: null,
      status: response.status,
    };
  } catch {
    return {
      data: null,
      error: "network_error",
      status: null,
    };
  }
}

export async function getRun(runId: string): Promise<RunSummary | null> {
  return safeFetch<RunSummary | null>(`/runs/${runId}`, null);
}

export async function getRunResult(runId: string): Promise<ApiResult<RunSummary>> {
  return fetchResult<RunSummary>(`/runs/${runId}`);
}

export async function listRuns(): Promise<RunSummary[]> {
  return safeFetch<RunSummary[]>("/runs", []);
}

export async function listRunsResult(): Promise<ApiResult<RunSummary[]>> {
  return fetchResult<RunSummary[]>("/runs");
}

export async function getTimeline(
  runId: string,
  filter?: TimelineFilter,
): Promise<TimelineResponse> {
  const params = buildTimelineParams(filter);
  const query = params.toString() ? `?${params.toString()}` : "";
  return safeFetch(`/runs/${runId}/timeline${query}`, { run_id: runId, events: [], total: 0, filtered: 0 });
}

export async function getTimelineResult(
  runId: string,
  filter?: TimelineFilter,
): Promise<ApiResult<TimelineResponse>> {
  const params = buildTimelineParams(filter);
  const query = params.toString() ? `?${params.toString()}` : "";
  return fetchResult<TimelineResponse>(`/runs/${runId}/timeline${query}`);
}

function buildTimelineParams(filter?: TimelineFilter): URLSearchParams {
  const params = new URLSearchParams();
  if (!filter) return params;
  if (filter.tick_from != null) params.set("tick_from", String(filter.tick_from));
  if (filter.tick_to != null) params.set("tick_to", String(filter.tick_to));
  if (filter.event_type) params.set("event_type", filter.event_type);
  if (filter.agent_id) params.set("agent_id", filter.agent_id);
  if (filter.limit != null) params.set("limit", String(filter.limit));
  if (filter.offset != null) params.set("offset", String(filter.offset));
  return params;
}

export async function getRunEventsResult(
  runId: string,
  eventType?: string,
  limit = 500,
): Promise<ApiResult<{ run_id: string; events: WorldEvent[]; total: number }>> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (eventType) params.set("event_type", eventType);
  return fetchResult<{ run_id: string; events: WorldEvent[]; total: number }>(
    `/runs/${runId}/events?${params.toString()}`,
  );
}

export async function getWorld(runId: string): Promise<WorldSnapshot | null> {
  return safeFetch<WorldSnapshot | null>(`/runs/${runId}/world`, null);
}

export async function getWorldResult(runId: string): Promise<ApiResult<WorldSnapshot>> {
  return fetchResult<WorldSnapshot>(`/runs/${runId}/world`);
}

export async function getDirectorMemoriesResult(
  runId: string,
  limit = 50,
): Promise<ApiResult<{ run_id: string; memories: DirectorMemory[]; total: number }>> {
  return fetchResult<{ run_id: string; memories: DirectorMemory[]; total: number }>(
    `/runs/${runId}/director/memories?limit=${limit}`,
  );
}

export async function getAgent(runId: string, agentId: string): Promise<AgentDetails | null> {
  return safeFetch<AgentDetails | null>(`/runs/${runId}/agents/${agentId}`, null);
}

export async function getAgentResult(
  runId: string,
  agentId: string,
): Promise<ApiResult<AgentDetails>> {
  return fetchResult<AgentDetails>(`/runs/${runId}/agents/${agentId}`);
}

export async function listAgents(runId: string): Promise<{ run_id: string; agents: AgentSummary[] }> {
  return safeFetch(`/runs/${runId}/agents`, { run_id: runId, agents: [] });
}

export async function listAgentsResult(
  runId: string,
): Promise<ApiResult<{ run_id: string; agents: AgentSummary[] }>> {
  return fetchResult<{ run_id: string; agents: AgentSummary[] }>(`/runs/${runId}/agents`);
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

export async function createRunResult(
  name: string,
  scenarioType = "truman_world",
  seedDemo = true,
  tickMinutes = 5,
): Promise<ApiResult<CreateRunResponse>> {
  return postResult<CreateRunResponse>("/runs", {
    name,
    scenario_type: scenarioType,
    seed_demo: seedDemo,
    tick_minutes: tickMinutes,
  });
}

export async function startRun(runId: string): Promise<RunSummary | null> {
  return safePost<RunSummary | null>(`/runs/${runId}/start`, {}, null);
}

export async function startRunResult(runId: string): Promise<ApiResult<RunSummary>> {
  return postResult<RunSummary>(`/runs/${runId}/start`, {});
}

export async function pauseRun(runId: string): Promise<RunSummary | null> {
  return safePost<RunSummary | null>(`/runs/${runId}/pause`, {}, null);
}

export async function pauseRunResult(runId: string): Promise<ApiResult<RunSummary>> {
  return postResult<RunSummary>(`/runs/${runId}/pause`, {});
}

export async function resumeRun(runId: string): Promise<RunSummary | null> {
  return safePost<RunSummary | null>(`/runs/${runId}/resume`, {}, null);
}

export async function resumeRunResult(runId: string): Promise<ApiResult<RunSummary>> {
  return postResult<RunSummary>(`/runs/${runId}/resume`, {});
}

export async function advanceRunTick(runId: string): Promise<TickResponse | null> {
  return safePost<TickResponse | null>(`/runs/${runId}/tick`, {}, null);
}

export async function advanceRunTickResult(runId: string): Promise<ApiResult<TickResponse>> {
  return postResult<TickResponse>(`/runs/${runId}/tick`, {});
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

export async function injectDirectorEventResult(
  runId: string,
  input: {
    event_type: string;
    payload: Record<string, unknown>;
    location_id?: string;
    importance?: number;
  },
): Promise<ApiResult<{ run_id: string; status: string }>> {
  return postResult<{ run_id: string; status: string }>(`/runs/${runId}/director/events`, input);
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

async function deleteResult<T>(path: string): Promise<ApiResult<T>> {
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
      return {
        data: null,
        error: response.status === 404 ? "not_found" : "request_failed",
        status: response.status,
      };
    }

    return {
      data: (await response.json()) as T,
      error: null,
      status: response.status,
    };
  } catch {
    return {
      data: null,
      error: "network_error",
      status: null,
    };
  }
}

export async function deleteRun(runId: string): Promise<{ run_id: string; status: string } | null> {
  return safeDelete<{ run_id: string; status: string } | null>(`/runs/${runId}`, null);
}

export async function deleteRunResult(
  runId: string,
): Promise<ApiResult<{ run_id: string; status: string }>> {
  return deleteResult<{ run_id: string; status: string }>(`/runs/${runId}`);
}

export async function restoreAllRuns(): Promise<RunSummary[]> {
  return safePost<RunSummary[]>('/runs/restore-all', {}, []);
}

export async function restoreAllRunsResult(): Promise<ApiResult<RunSummary[]>> {
  return postResult<RunSummary[]>("/runs/restore-all", {});
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

export async function fetchApiResult<T>(url: string): Promise<ApiResult<T>> {
  return fetchResultUrl<T>(url);
}
