import type {
  AgentDetails,
  AgentSummary,
  CreateRunResponse,
  DirectorMemory,
  RunSummary,
  SystemMetrics,
  SystemOverview,
  TickResponse,
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
  SystemMetrics,
  SystemOverview,
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

declare global {
  interface Window {
    __TRUMANWORLD_CONFIG__?: {
      apiBaseUrl?: string;
    };
  }
}

const DEFAULT_API_BASE_URL = "/api";

function resolveApiBaseUrl() {
  const runtimeBaseUrl =
    typeof window !== "undefined"
      ? window.__TRUMANWORLD_CONFIG__?.apiBaseUrl?.replace(/\/$/, "")
      : undefined;
  const publicBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "");

  return runtimeBaseUrl ?? publicBaseUrl ?? DEFAULT_API_BASE_URL;
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
  sinceTick?: number,
): Promise<ApiResult<{ run_id: string; events: WorldEvent[]; total: number; latest_tick: number }>> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (eventType) params.set("event_type", eventType);
  if (sinceTick != null) params.set("since_tick", String(sinceTick));
  return fetchResult<{ run_id: string; events: WorldEvent[]; total: number; latest_tick: number }>(
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

function readMetricValue(metricsText: string, metricName: string): number {
  const pattern = new RegExp(`^${metricName}\\s+([0-9.eE+-]+)$`, "m");
  const match = metricsText.match(pattern);
  return match ? Number(match[1]) : 0;
}

function readLabeledMetricValue(
  metricsText: string,
  metricName: string,
  labels: Record<string, string>,
): number {
  const labelsPattern = Object.entries(labels)
    .map(([key, value]) => `${key}="${value}"`)
    .join(",");
  const pattern = new RegExp(`^${metricName}\\{${labelsPattern}\\}\\s+([0-9.eE+-]+)$`, "m");
  const match = metricsText.match(pattern);
  return match ? Number(match[1]) : 0;
}

export async function getSystemMetrics(): Promise<SystemMetrics | null> {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5000);

    const response = await fetch(buildApiUrl("/metrics"), {
      cache: "no-store",
      signal: controller.signal,
      headers: {
        Accept: "text/plain",
      },
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      return null;
    }

    const metricsText = await response.text();

    return {
      processResidentMemoryBytes: readMetricValue(metricsText, "process_resident_memory_bytes"),
      processVirtualMemoryBytes: readMetricValue(metricsText, "process_virtual_memory_bytes"),
      processCpuSecondsTotal: readMetricValue(metricsText, "process_cpu_seconds_total"),
      processOpenFileDescriptors: readMetricValue(metricsText, "process_open_fds") || null,
      activeRuns: readMetricValue(metricsText, "trumanworld_active_runs"),
      tickTotal: {
        inlineSuccess: readLabeledMetricValue(metricsText, "trumanworld_tick_total", {
          mode: "inline",
          status: "success",
        }),
        inlineError: readLabeledMetricValue(metricsText, "trumanworld_tick_total", {
          mode: "inline",
          status: "error",
        }),
        isolatedSuccess: readLabeledMetricValue(metricsText, "trumanworld_tick_total", {
          mode: "isolated",
          status: "success",
        }),
        isolatedError: readLabeledMetricValue(metricsText, "trumanworld_tick_total", {
          mode: "isolated",
          status: "error",
        }),
      },
      llmCallTotal: readMetricValue(metricsText, "trumanworld_llm_call_total"),
      llmCostUsdTotal: readMetricValue(metricsText, "trumanworld_llm_cost_usd_total"),
      llmTokensTotal: {
        input: readLabeledMetricValue(metricsText, "trumanworld_llm_tokens_total", {
          token_type: "input",
        }),
        output: readLabeledMetricValue(metricsText, "trumanworld_llm_tokens_total", {
          token_type: "output",
        }),
        cacheRead: readLabeledMetricValue(metricsText, "trumanworld_llm_tokens_total", {
          token_type: "cache_read",
        }),
        cacheCreation: readLabeledMetricValue(metricsText, "trumanworld_llm_tokens_total", {
          token_type: "cache_creation",
        }),
      },
      scrapedAt: Date.now(),
    };
  } catch {
    return null;
  }
}

function toCamelCaseSystemOverview(input: {
  collected_at: number;
  components: Record<
    string,
    {
      status: "available" | "unavailable";
      rss_bytes: number;
      vms_bytes: number;
      cpu_seconds: number;
      cpu_percent: number;
      process_count: number;
    }
  >;
}): SystemOverview {
  return {
    collectedAt: input.collected_at,
    components: {
      backend: {
        status: input.components.backend.status,
        rssBytes: input.components.backend.rss_bytes,
        vmsBytes: input.components.backend.vms_bytes,
        cpuSeconds: input.components.backend.cpu_seconds,
        cpuPercent: input.components.backend.cpu_percent,
        processCount: input.components.backend.process_count,
      },
      frontend: {
        status: input.components.frontend.status,
        rssBytes: input.components.frontend.rss_bytes,
        vmsBytes: input.components.frontend.vms_bytes,
        cpuSeconds: input.components.frontend.cpu_seconds,
        cpuPercent: input.components.frontend.cpu_percent,
        processCount: input.components.frontend.process_count,
      },
      postgres: {
        status: input.components.postgres.status,
        rssBytes: input.components.postgres.rss_bytes,
        vmsBytes: input.components.postgres.vms_bytes,
        cpuSeconds: input.components.postgres.cpu_seconds,
        cpuPercent: input.components.postgres.cpu_percent,
        processCount: input.components.postgres.process_count,
      },
      total: {
        status: input.components.total.status,
        rssBytes: input.components.total.rss_bytes,
        vmsBytes: input.components.total.vms_bytes,
        cpuSeconds: input.components.total.cpu_seconds,
        cpuPercent: input.components.total.cpu_percent,
        processCount: input.components.total.process_count,
      },
    },
  };
}

export async function getSystemOverview(): Promise<SystemOverview | null> {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5000);

    const response = await fetch(buildApiUrl("/system/overview"), {
      cache: "no-store",
      signal: controller.signal,
      headers: {
        Accept: "application/json",
      },
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      return null;
    }

    const payload = (await response.json()) as {
      collected_at: number;
      components: Record<
        string,
        {
          status: "available" | "unavailable";
          rss_bytes: number;
          vms_bytes: number;
          cpu_seconds: number;
          cpu_percent: number;
          process_count: number;
        }
      >;
    };
    return toCamelCaseSystemOverview(payload);
  } catch {
    return null;
  }
}
