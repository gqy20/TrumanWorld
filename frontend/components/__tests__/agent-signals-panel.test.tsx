import { fireEvent, render, screen } from "@testing-library/react";

import { AgentSignalsPanel } from "@/components/agent-signals-panel";
import type { AgentDetails } from "@/lib/types";

jest.mock("@/lib/event-utils", () => ({
  describeAgentEvent: (event: { event_type: string; payload: Record<string, unknown> }) =>
    String(event.payload.message ?? `${event.event_type} event`),
}));

describe("AgentSignalsPanel", () => {
  const agent: AgentDetails = {
    run_id: "run-1",
    agent_id: "alice",
    name: "Alice",
    recent_events: [
      {
        id: "event-speech",
        tick_no: 3,
        event_type: "speech",
        payload: { message: "Secret meeting tonight" },
      },
      {
        id: "event-move",
        tick_no: 2,
        event_type: "move",
        payload: { message: "Moved to cafe" },
      },
      {
        id: "event-work",
        tick_no: 1,
        event_type: "work",
        payload: { message: "Worked quietly" },
      },
    ],
    memories: [
      {
        id: "memory-secret",
        memory_type: "reflection",
        memory_category: "long_term",
        content: "Remembered Bob's secret plan.",
        importance: 0.9,
        related_agent_id: "bob",
        related_agent_name: "Bob",
      },
      {
        id: "memory-routine",
        memory_type: "episodic_short",
        memory_category: "short_term",
        content: "Worked during this tick.",
        importance: 0.1,
      },
    ],
    relationships: [],
  };

  it("filters events by type and hides routine events", () => {
    render(<AgentSignalsPanel agent={agent} />);

    expect(screen.getByText("Secret meeting tonight")).toBeInTheDocument();
    expect(screen.getByText("Moved to cafe")).toBeInTheDocument();
    expect(screen.getByText("Worked quietly")).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole("button", { name: /筛选/ })[0]);
    fireEvent.change(screen.getByLabelText("事件类型"), {
      target: { value: "speech" },
    });

    expect(screen.getByText("Secret meeting tonight")).toBeInTheDocument();
    expect(screen.queryByText("Moved to cafe")).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("事件类型"), {
      target: { value: "" },
    });
    fireEvent.click(screen.getByLabelText("隐藏例行事件"));

    expect(screen.queryByText("Worked quietly")).not.toBeInTheDocument();
    expect(screen.getByText("Moved to cafe")).toBeInTheDocument();
  });

  it("filters memories by category, query, and minimum importance", () => {
    render(<AgentSignalsPanel agent={agent} />);

    expect(screen.getByText("Remembered Bob's secret plan.")).toBeInTheDocument();
    expect(screen.getByText("Worked during this tick.")).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole("button", { name: /筛选/ })[1]);
    fireEvent.change(screen.getByLabelText("层级"), {
      target: { value: "long_term" },
    });
    expect(screen.getByText("Remembered Bob's secret plan.")).toBeInTheDocument();
    expect(screen.queryByText("Worked during this tick.")).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("搜索"), {
      target: { value: "bob" },
    });
    expect(screen.getByText("Remembered Bob's secret plan.")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("最低重要性"), {
      target: { value: "0.95" },
    });
    expect(screen.getByText("暂无匹配记忆")).toBeInTheDocument();
  });
});
