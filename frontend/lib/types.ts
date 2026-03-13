import type { EventType } from "@/lib/simulation-protocol";

export type RunSummary = {
  id: string;
  name: string;
  status: string;
  scenario_type?: string;
  current_tick?: number;
  tick_minutes?: number;
  was_running_before_restart?: boolean;
  agent_count?: number;
  location_count?: number;
  event_count?: number;
  started_at?: string | null; // ISO8601 UTC, 最近一次启动时间
  elapsed_seconds?: number;   // 已累计运行秒数（暂停期间停止累加）
};

export type CreateRunResponse = {
  id: string;
  name: string;
  status: string;
  scenario_type?: string;
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
  event_type: EventType;
  importance?: number;
  payload: Record<string, unknown>;
  world_time?: string;  // HH:MM
  world_date?: string;  // YYYY-MM-DD
};

export type TimelineRunInfo = {
  current_tick: number;
  tick_minutes: number;
  world_start_iso: string;
  current_world_time_iso: string;
};

export type TimelineResponse = {
  run_id: string;
  events: TimelineEvent[];
  total: number;
  filtered: number;
  run_info?: TimelineRunInfo;
};

export type TimelineFilter = {
  tick_from?: number;
  tick_to?: number;
  world_datetime_from?: string;
  world_datetime_to?: string;
  event_type?: string;
  agent_id?: string;
  limit?: number;
  offset?: number;
  order_desc?: boolean;
};

export type WorldClock = {
  iso: string;
  date: string;
  time: string;
  year: number;
  month: number;
  day: number;
  hour: number;
  minute: number;
  weekday: number;
  weekday_name: string;
  weekday_name_cn: string;
  is_weekend: boolean;
  time_period: string;
  time_period_cn: string;
};

export type AgentSummary = {
  id: string;
  name: string;
  occupation?: string;
  current_goal?: string;
  current_location_id?: string;
  status?: Record<string, unknown>;
  config_id?: string; // agent 配置 ID，用于加载自定义 logo
};

export type WorldEvent = {
  id: string;
  tick_no: number;
  event_type: EventType;
  location_id?: string;
  actor_agent_id?: string;
  target_agent_id?: string;
  actor_name?: string;
  target_name?: string;
  location_name?: string;
  payload: Record<string, unknown>;
};

export type WorldLocation = {
  id: string;
  name: string;
  location_type: string;
  x: number;
  y: number;
  capacity: number;
  occupants: AgentSummary[];
};

export type WorldSnapshot = {
  run: RunSummary;
  world_clock?: WorldClock;
  locations: WorldLocation[];
  recent_events: WorldEvent[];
  director_stats?: {
    total: number;
    executed: number; // 已消费数量，沿用后端字段名兼容现有接口
    execution_rate: number; // 消费率，沿用后端字段名兼容现有接口
  };
  daily_stats?: {
    talk_count: number;
    move_count: number;
    rejection_count: number;
    total_input_tokens: number;
    total_output_tokens: number;
    total_cache_read_tokens: number;
    total_cache_creation_tokens: number;
  };
  health_metrics_config?: {
    continuity_penalty_factor: number;
    continuity_warning_threshold: number;
    continuity_trend_down_threshold: number;
    continuity_trend_stable_threshold: number;
    social_baseline_talks_per_person_per_day: number;
    social_trend_up_threshold: number;
    social_trend_stable_threshold: number;
    // Location heat display
    heat_normalization_baseline: number;
    heat_threshold_very_active: number;
    heat_threshold_active: number;
    heat_threshold_mild: number;
    heat_glow_threshold: number;
    // UI config
    ui_location_detail_max_events: number;
    ui_intelligence_stream_max_events: number;
    ui_intelligence_stream_poll_interval: number;
    ui_director_panel_max_memories: number;
  };
};

export type WorldPulse = {
  run: RunSummary;
  world_clock?: WorldClock;
  daily_stats?: WorldSnapshot["daily_stats"];
};

export type DirectorMemory = {
  id: string;
  tick_no: number;
  scene_goal: string;
  priority: string;
  urgency: string;
  message_hint?: string | null;
  target_agent_id?: string | null;
  target_agent_name?: string | null;
  target_cast_ids: string[];
  target_cast_names: string[];
  location_hint?: string | null;
  location_name?: string | null;
  reason?: string | null;
  was_executed: boolean; // 是否已被某个 tick 消费
  delivery_status: "queued" | "consumed" | "expired";
  effectiveness_score?: number | null;
  trigger_suspicion_score: number;
  trigger_continuity_risk: string;
  cooldown_ticks: number;
  cooldown_until_tick?: number | null;
  created_at: string;
};

export type SystemMetrics = {
  processResidentMemoryBytes: number;
  processVirtualMemoryBytes: number;
  processCpuSecondsTotal: number;
  processOpenFileDescriptors?: number | null;
  activeRuns: number;
  tickTotal: {
    inlineSuccess: number;
    inlineError: number;
    isolatedSuccess: number;
    isolatedError: number;
  };
  llmCallTotal: number;
  llmCostUsdTotal: number;
  llmTokensTotal: {
    input: number;
    output: number;
    cacheRead: number;
    cacheCreation: number;
  };
  scrapedAt: number;
};

export type SystemOverviewComponent = {
  status: "available" | "unavailable";
  rssBytes: number;
  uniqueBytes?: number | null;
  vmsBytes: number;
  cpuSeconds: number;
  cpuPercent: number;
  processCount: number;
};

export type SystemOverview = {
  collectedAt: number;
  components: {
    backend: SystemOverviewComponent;
    frontend: SystemOverviewComponent;
    postgres: SystemOverviewComponent;
    total: SystemOverviewComponent;
  };
};

export type AgentRecentEvent = {
  id: string;
  tick_no: number;
  event_type: EventType;
  actor_agent_id?: string;
  actor_name?: string;
  target_agent_id?: string;
  target_name?: string;
  location_id?: string;
  location_name?: string;
  payload: Record<string, unknown>;
};

export type AgentMemory = {
  id: string;
  memory_type: string;
  memory_category: string;
  summary?: string;
  content: string;
  importance?: number;
  event_importance?: number;
  self_relevance?: number;
  streak_count?: number;
  related_agent_id?: string;
  related_agent_name?: string;
  created_at?: string;
};

export type AgentRelationship = {
  other_agent_id: string;
  other_agent_name?: string;
  familiarity: number;
  trust: number;
  affinity: number;
  relation_type: string;
};

export type AgentDetails = {
  run_id: string;
  agent_id: string;
  name: string;
  occupation?: string;
  current_goal?: string;
  status?: Record<string, unknown>;
  config_id?: string; // agent 配置 ID，用于加载自定义 logo
  personality?: Record<string, unknown>;
  profile?: Record<string, unknown>;
  recent_events: AgentRecentEvent[];
  memories: AgentMemory[];
  relationships: AgentRelationship[];
};
