import { aggregateStoryChapters } from "@/lib/world-insights";
import type { WorldSnapshot } from "@/lib/types";

function buildWorld(events: WorldSnapshot["recent_events"]): WorldSnapshot {
  return {
    run: {
      id: "run-1",
      name: "Test Run",
      status: "paused",
      current_tick: 20,
      tick_minutes: 5,
    },
    world_clock: {
      iso: "2026-03-21T12:00:00Z",
      date: "2026-03-21",
      time: "12:00",
      year: 2026,
      month: 3,
      day: 21,
      hour: 12,
      minute: 0,
      weekday: 6,
      weekday_name: "Saturday",
      weekday_name_cn: "周六",
      is_weekend: true,
      time_period: "noon",
      time_period_cn: "正午",
    },
    subject_agent_id: null,
    locations: [
      {
        id: "cafe",
        name: "咖啡店",
        location_type: "cafe",
        x: 0,
        y: 0,
        capacity: 10,
        occupants: [
          { id: "alice", name: "Alice" },
          { id: "bob", name: "Bob" },
        ],
      },
    ],
    recent_events: events,
  };
}

describe("aggregateStoryChapters", () => {
  it("keeps relationship impact explanations on social story events", () => {
    const chapters = aggregateStoryChapters(
      buildWorld([
        {
          id: "evt-1",
          tick_no: 20,
          event_type: "talk",
          actor_agent_id: "alice",
          target_agent_id: "bob",
          location_id: "cafe",
          payload: {
            relationship_impact: {
              summary: "High-risk social contact reduced trust and affinity gains.",
            },
            rule_evaluation: {
              decision: "soft_risk",
              reason: "late_night_talk_risk",
            },
          },
        },
      ]),
    );

    expect(chapters).toHaveLength(1);
    expect(chapters[0].events[0].explanations).toEqual([
      {
        kind: "relationship",
        text: "High-risk social contact reduced trust and affinity gains.",
        tone: "rose",
      },
      {
        kind: "risk",
        text: "深夜社交风险",
        tone: "amber",
      },
    ]);
  });

  it("adds a warning highlight when a chapter contains risk-tagged social interactions", () => {
    const chapters = aggregateStoryChapters(
      buildWorld([
        {
          id: "evt-1",
          tick_no: 20,
          event_type: "talk",
          actor_agent_id: "alice",
          target_agent_id: "bob",
          location_id: "cafe",
          payload: {
            rule_evaluation: {
              decision: "soft_risk",
              reason: "late_night_talk_risk",
            },
          },
        },
      ]),
    );

    expect(chapters[0].highlights).toContainEqual({
      type: "warning",
      description: "1 次风险社交",
    });
  });
});
