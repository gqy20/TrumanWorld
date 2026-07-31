import type {
  RunSummary,
  ScenarioSummary,
  TimelineEvent,
  TimelineResponse,
  WorldSnapshot,
} from "@/lib/types";

export function makeScenarioSummary(overrides: Partial<ScenarioSummary> = {}): ScenarioSummary {
  return {
    id: "narrative_world",
    name: "Narrative World",
    version: 1,
    ...overrides,
  };
}

export function makeRunSummary(overrides: Partial<RunSummary> = {}): RunSummary {
  return {
    id: "run-1",
    name: "Campus Morning",
    status: "running",
    scenario_type: "narrative_world",
    current_tick: 24,
    tick_minutes: 5,
    agent_count: 1,
    location_count: 2,
    event_count: 2,
    elapsed_seconds: 120,
    started_at: "2026-03-02T06:00:00Z",
    created_at: "2026-03-02T06:00:00Z",
    ...overrides,
  };
}

export function makeWorldSnapshot(overrides: Partial<WorldSnapshot> = {}): WorldSnapshot {
  const run = overrides.run ?? makeRunSummary();

  return {
    run,
    world_clock: {
      iso: "2026-03-02T08:00:00Z",
      date: "2026-03-02",
      time: "08:00",
      year: 2026,
      month: 3,
      day: 2,
      hour: 8,
      minute: 0,
      weekday: 1,
      weekday_name: "Monday",
      weekday_name_cn: "周一",
      is_weekend: false,
      time_period: "morning",
      time_period_cn: "上午",
    },
    subject_agent_id: "agent-1",
    locations: [
      {
        id: "cafe",
        name: "Cafe",
        location_type: "cafe",
        x: 10,
        y: 20,
        capacity: 6,
        occupants: [
          {
            id: "agent-1",
            name: "Mei Lin",
            occupation: "Student",
            current_goal: "talk",
            current_location_id: "cafe",
            status: { alert_score: 0.2 },
          },
        ],
      },
      {
        id: "library",
        name: "Library",
        location_type: "library",
        x: 30,
        y: 40,
        capacity: 8,
        occupants: [],
      },
    ],
    recent_events: [
      {
        id: "event-1",
        tick_no: 24,
        event_type: "talk",
        location_id: "cafe",
        actor_agent_id: "agent-1",
        actor_name: "Mei Lin",
        payload: { message: "Good morning" },
      },
      {
        id: "event-2",
        tick_no: 23,
        event_type: "move",
        location_id: "cafe",
        actor_agent_id: "agent-1",
        actor_name: "Mei Lin",
        payload: { from_location_id: "library", to_location_id: "cafe" },
      },
    ],
    director_stats: {
      total: 2,
      executed: 1,
      execution_rate: 0.5,
    },
    daily_stats: {
      talk_count: 4,
      move_count: 2,
      rejection_count: 0,
      total_input_tokens: 1000,
      total_output_tokens: 500,
      total_reasoning_tokens: 0,
      total_cache_read_tokens: 0,
      total_cache_creation_tokens: 0,
    },
    ...overrides,
  };
}

export function makeTimelineEvent(overrides: Partial<TimelineEvent> = {}): TimelineEvent {
  return {
    id: "timeline-event-1",
    tick_no: 24,
    event_type: "talk",
      importance: 0.8,
    world_time: "08:00",
    world_date: "2026-03-02",
    payload: {
      actor_name: "Mei Lin",
      target_name: "Jon Park",
      location_name: "Cafe",
      message: "Good morning",
    },
    ...overrides,
  };
}

export function makeTimelineResponse(
  overrides: Partial<TimelineResponse> = {},
): TimelineResponse {
  const events = overrides.events ?? [
    makeTimelineEvent(),
    makeTimelineEvent({
      id: "timeline-event-2",
      tick_no: 23,
      event_type: "move",
      importance: 0.4,
      world_time: "07:55",
      payload: {
        actor_name: "Mei Lin",
        location_name: "Library",
        from_location_name: "Library",
        to_location_name: "Cafe",
      },
    }),
  ];

  return {
    run_id: "run-1",
    events,
    total: events.length,
    filtered: events.length,
    run_info: {
      current_tick: 24,
      tick_minutes: 5,
      world_start_iso: "2026-03-02T06:00:00Z",
      current_world_time_iso: "2026-03-02T08:00:00Z",
    },
    ...overrides,
  };
}
