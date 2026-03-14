import { render, screen } from "@testing-library/react";
import { EventCard } from "@/components/event-card";
import type { WorldEvent } from "@/lib/types";
import * as eventUtils from "@/lib/event-utils";

// Mock framer-motion to avoid animation issues in tests
jest.mock("framer-motion", () => ({
  motion: {
    div: ({ children, className, style }: { children: React.ReactNode; className?: string; style?: React.CSSProperties }) => (
      <div className={className} style={style}>
        {children}
      </div>
    ),
  },
}));

// Mock event utils
jest.mock("@/lib/event-utils");
jest.mock("@/lib/simulation-protocol", () => ({
  EVENT_CONVERSATION_JOINED: "conversation_joined",
  EVENT_CONVERSATION_STARTED: "conversation_started",
  EVENT_SPEECH: "speech",
  EVENT_TALK: "talk",
}));

const mockGetEventMeta = eventUtils.getEventMeta as jest.MockedFunction<typeof eventUtils.getEventMeta>;
const mockDescribeWorldEvent = eventUtils.describeWorldEvent as jest.MockedFunction<typeof eventUtils.describeWorldEvent>;

describe("EventCard", () => {
  const mockEvent: WorldEvent = {
    id: "event-1",
    event_type: "move",
    tick_no: 5,
    actor_agent_id: "agent-1",
    target_agent_id: undefined,
    location_id: "loc-1",
    payload: {},
  };

  const agentNameMap = { "agent-1": "Alice", "agent-2": "Bob" };
  const locationNameMap = { "loc-1": "咖啡店", "loc-2": "公园" };

  beforeEach(() => {
    jest.clearAllMocks();
    mockGetEventMeta.mockReturnValue({
      icon: "🚶",
      label: "移动",
      chip: "bg-emerald-50 text-emerald-700 border border-emerald-100",
      color: "#10b981",
    });
    mockDescribeWorldEvent.mockReturnValue("Alice 移动到了 咖啡店");
  });

  it("renders event description", () => {
    render(
      <EventCard
        event={mockEvent}
        index={0}
        isLatest={false}
        agentNameMap={agentNameMap}
        locationNameMap={locationNameMap}
      />
    );

    expect(screen.getByText("Alice 移动到了 咖啡店")).toBeInTheDocument();
  });

  it("renders event type label", () => {
    render(
      <EventCard
        event={mockEvent}
        index={0}
        isLatest={false}
        agentNameMap={agentNameMap}
        locationNameMap={locationNameMap}
      />
    );

    expect(screen.getByText("移动")).toBeInTheDocument();
  });

  it("renders tick number", () => {
    render(
      <EventCard
        event={mockEvent}
        index={0}
        isLatest={false}
        agentNameMap={agentNameMap}
        locationNameMap={locationNameMap}
      />
    );

    expect(screen.getByText(/T5/)).toBeInTheDocument();
  });

  it("renders sim time when provided", () => {
    render(
      <EventCard
        event={mockEvent}
        index={0}
        isLatest={false}
        agentNameMap={agentNameMap}
        locationNameMap={locationNameMap}
        simTime="09:30"
      />
    );

    expect(screen.getByText(/T5 · 09:30/)).toBeInTheDocument();
  });

  it("renders actor agent tag", () => {
    render(
      <EventCard
        event={mockEvent}
        index={0}
        isLatest={false}
        agentNameMap={agentNameMap}
        locationNameMap={locationNameMap}
      />
    );

    expect(screen.getByText("Alice")).toBeInTheDocument();
  });

  it("renders target agent tag when present", () => {
    const eventWithTarget: WorldEvent = {
      ...mockEvent,
      target_agent_id: "agent-2",
    };

    render(
      <EventCard
        event={eventWithTarget}
        index={0}
        isLatest={false}
        agentNameMap={agentNameMap}
        locationNameMap={locationNameMap}
      />
    );

    expect(screen.getByText(/→ Bob/)).toBeInTheDocument();
  });

  it("renders location tag when present", () => {
    render(
      <EventCard
        event={mockEvent}
        index={0}
        isLatest={false}
        agentNameMap={agentNameMap}
        locationNameMap={locationNameMap}
      />
    );

    expect(screen.getByText(/📍 咖啡店/)).toBeInTheDocument();
  });

  it("renders message when payload has message", () => {
    const eventWithMessage: WorldEvent = {
      ...mockEvent,
      payload: { message: "你好，今天天气不错" },
    };

    render(
      <EventCard
        event={eventWithMessage}
        index={0}
        isLatest={false}
        agentNameMap={agentNameMap}
        locationNameMap={locationNameMap}
      />
    );

    expect(screen.getByText(/「你好，今天天气不错」/)).toBeInTheDocument();
  });

  it("renders importance star when importance >= 7", () => {
    const eventWithImportance: WorldEvent = {
      ...mockEvent,
      payload: { importance: 8 },
    };

    render(
      <EventCard
        event={eventWithImportance}
        index={0}
        isLatest={false}
        agentNameMap={agentNameMap}
        locationNameMap={locationNameMap}
      />
    );

    expect(screen.getByText(/⭐ 8/)).toBeInTheDocument();
  });

  it("does not render importance star when importance < 7", () => {
    const eventWithLowImportance: WorldEvent = {
      ...mockEvent,
      payload: { importance: 5 },
    };

    render(
      <EventCard
        event={eventWithLowImportance}
        index={0}
        isLatest={false}
        agentNameMap={agentNameMap}
        locationNameMap={locationNameMap}
      />
    );

    expect(screen.queryByText(/⭐/)).not.toBeInTheDocument();
  });
});
