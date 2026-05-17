import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import TimelinePage from "@/app/runs/[runId]/timeline/page";
import { getTimelineResult, listAgentsResult } from "@/lib/api";
import type { TimelineResponse } from "@/lib/types";
import { makeTimelineResponse } from "@/test-utils/app/fixtures";
import { errorResult, okResult } from "@/test-utils/app/render";

jest.mock("next/navigation", () => ({
  useParams: () => ({ runId: "run-1" }),
}));

jest.mock("@/lib/api", () => {
  const actual = jest.requireActual("@/lib/api");

  return {
    ...actual,
    getTimelineResult: jest.fn(),
    listAgentsResult: jest.fn(),
  };
});

const timeline = makeTimelineResponse();

describe("TimelinePage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (getTimelineResult as jest.MockedFunction<typeof getTimelineResult>)
      .mockResolvedValue(okResult(timeline));
    (listAgentsResult as jest.MockedFunction<typeof listAgentsResult>)
      .mockResolvedValue(okResult({
        run_id: "run-1",
        agents: [
          {
            id: "agent-1",
            name: "Mei Lin",
            occupation: "Student",
          },
        ],
      }));
  });

  it("renders initial timeline data and grouped events", async () => {
    render(<TimelinePage />);

    expect(await screen.findByRole("heading", { name: "时间线" })).toBeInTheDocument();
    expect(screen.getByText("数据库总事件")).toBeInTheDocument();
    expect(screen.getByText("重要事件")).toBeInTheDocument();
    expect(await screen.findByText("时间步 24")).toBeInTheDocument();
    expect(screen.getByText("时间步 23")).toBeInTheDocument();
    expect(screen.getAllByText("Mei Lin").length).toBeGreaterThan(0);
    expect(screen.getByText("Jon Park")).toBeInTheDocument();
    expect(screen.getAllByText(/Cafe/).length).toBeGreaterThan(0);

    expect(getTimelineResult).toHaveBeenCalledWith(
      "run-1",
      expect.objectContaining({
        limit: 250,
        offset: 0,
        order_desc: true,
      }),
    );
  });

  it("applies event, agent, and tick filters when searching", async () => {
    render(<TimelinePage />);

    await screen.findByRole("heading", { name: "时间线" });

    fireEvent.change(screen.getByLabelText("事件类型"), { target: { value: "move" } });
    fireEvent.change(screen.getByLabelText("角色"), { target: { value: "agent-1" } });
    fireEvent.change(screen.getByPlaceholderText("起始"), { target: { value: "10" } });
    fireEvent.change(screen.getByPlaceholderText("结束"), { target: { value: "24" } });

    const filteredTimeline = makeTimelineResponse({
      events: [
        timeline.events[1],
      ],
      filtered: 1,
      total: 2,
    });
    (getTimelineResult as jest.MockedFunction<typeof getTimelineResult>)
      .mockResolvedValueOnce(okResult(filteredTimeline));

    fireEvent.click(screen.getByRole("button", { name: "检索" }));

    await waitFor(() => {
      expect(getTimelineResult).toHaveBeenLastCalledWith(
        "run-1",
        expect.objectContaining({
          agent_id: "agent-1",
          event_type: "move",
          tick_from: 10,
          tick_to: 24,
          limit: 250,
          offset: 0,
          order_desc: true,
        }),
      );
    });
    expect(await screen.findByText(/过滤后匹配/)).toBeInTheDocument();
  });

  it("shows a network error when the timeline request fails", async () => {
    (getTimelineResult as jest.MockedFunction<typeof getTimelineResult>)
      .mockResolvedValue(errorResult<TimelineResponse>("network_error"));

    render(<TimelinePage />);

    expect(await screen.findByText("网络错误")).toBeInTheDocument();
    expect(screen.queryByText("时间步 24")).not.toBeInTheDocument();
  });
});
