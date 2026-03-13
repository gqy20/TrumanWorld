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
  WorldPulse,
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
  WorldPulse,
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
const DEFAULT_INTERNAL_API_BASE_URL = "http://127.0.0.1:18080/api";

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

export function getInternalApiBaseUrl() {
  return process.env.INTERNAL_API_BASE_URL?.replace(/\/$/, "") ?? DEFAULT_INTERNAL_API_BASE_URL;
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

export async function getRunResult(runId: string): Promise<ApiResult<RunSummary>> {
  return fetchResult<RunSummary>(`/runs/${runId}`);
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
  if (filter.world_datetime_from) params.set("world_datetime_from", filter.world_datetime_from);
  if (filter.world_datetime_to) params.set("world_datetime_to", filter.world_datetime_to);
  if (filter.event_type) params.set("event_type", filter.event_type);
  if (filter.agent_id) params.set("agent_id", filter.agent_id);
  if (filter.limit != null) params.set("limit", String(filter.limit));
  if (filter.offset != null) params.set("offset", String(filter.offset));
  if (filter.order_desc != null) params.set("order_desc", String(filter.order_desc));
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

export async function getWorldResult(runId: string): Promise<ApiResult<WorldSnapshot>> {
  return fetchResult<WorldSnapshot>(`/runs/${runId}/world`);
}

export async function getWorldPulseResult(runId: string): Promise<ApiResult<WorldPulse>> {
  return fetchResult<WorldPulse>(`/runs/${runId}/world/pulse`);
}

export async function getDirectorMemoriesResult(
  runId: string,
  limit = 50,
): Promise<ApiResult<{ run_id: string; memories: DirectorMemory[]; total: number }>> {
  return fetchResult<{ run_id: string; memories: DirectorMemory[]; total: number }>(
    `/runs/${runId}/director/memories?limit=${limit}`,
  );
}

export async function getAgentResult(
  runId: string,
  agentId: string,
): Promise<ApiResult<AgentDetails>> {
  return fetchResult<AgentDetails>(`/runs/${runId}/agents/${agentId}`);
}

export async function listAgentsResult(
  runId: string,
): Promise<ApiResult<{ run_id: string; agents: AgentSummary[] }>> {
  return fetchResult<{ run_id: string; agents: AgentSummary[] }>(`/runs/${runId}/agents`);
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

export async function startRunResult(runId: string): Promise<ApiResult<RunSummary>> {
  return postResult<RunSummary>(`/runs/${runId}/start`, {});
}

export async function pauseRunResult(runId: string): Promise<ApiResult<RunSummary>> {
  return postResult<RunSummary>(`/runs/${runId}/pause`, {});
}

export async function resumeRunResult(runId: string): Promise<ApiResult<RunSummary>> {
  return postResult<RunSummary>(`/runs/${runId}/resume`, {});
}

export async function advanceRunTickResult(runId: string): Promise<ApiResult<TickResponse>> {
  return postResult<TickResponse>(`/runs/${runId}/tick`, {});
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

export async function deleteRunResult(
  runId: string,
): Promise<ApiResult<{ run_id: string; status: string }>> {
  return deleteResult<{ run_id: string; status: string }>(`/runs/${runId}`);
}

export async function restoreAllRunsResult(): Promise<ApiResult<RunSummary[]>> {
  return postResult<RunSummary[]>("/runs/restore-all", {});
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
      unique_bytes?: number | null;
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
        uniqueBytes: input.components.backend.unique_bytes ?? null,
        vmsBytes: input.components.backend.vms_bytes,
        cpuSeconds: input.components.backend.cpu_seconds,
        cpuPercent: input.components.backend.cpu_percent,
        processCount: input.components.backend.process_count,
      },
      frontend: {
        status: input.components.frontend.status,
        rssBytes: input.components.frontend.rss_bytes,
        uniqueBytes: input.components.frontend.unique_bytes ?? null,
        vmsBytes: input.components.frontend.vms_bytes,
        cpuSeconds: input.components.frontend.cpu_seconds,
        cpuPercent: input.components.frontend.cpu_percent,
        processCount: input.components.frontend.process_count,
      },
      postgres: {
        status: input.components.postgres.status,
        rssBytes: input.components.postgres.rss_bytes,
        uniqueBytes: input.components.postgres.unique_bytes ?? null,
        vmsBytes: input.components.postgres.vms_bytes,
        cpuSeconds: input.components.postgres.cpu_seconds,
        cpuPercent: input.components.postgres.cpu_percent,
        processCount: input.components.postgres.process_count,
      },
      total: {
        status: input.components.total.status,
        rssBytes: input.components.total.rss_bytes,
        uniqueBytes: input.components.total.unique_bytes ?? null,
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
