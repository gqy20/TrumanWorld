import { render, screen } from "@testing-library/react";
import { StoryTimeline } from "@/components/story-timeline";
import type { StoryChapter } from "@/lib/world-insights";

jest.mock("framer-motion", () => ({
  motion: {
    div: ({ children, className }: { children: React.ReactNode; className?: string }) => (
      <div className={className}>{children}</div>
    ),
    svg: ({ children, className }: { children: React.ReactNode; className?: string }) => (
      <svg className={className}>{children}</svg>
    ),
  },
  AnimatePresence: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

describe("StoryTimeline", () => {
  it("renders relationship and risk explanations for story events", () => {
    const chapters: StoryChapter[] = [
      {
        id: "chapter-1",
        timeLabel: "12:00",
        period: "noon",
        periodIcon: "☀️",
        periodName: "正午",
        highlights: [],
        events: [
          {
            id: "evt-1",
            tickNo: 20,
            time: "T20",
            type: "social",
            actorName: "Alice",
            targetName: "Bob",
            locationName: "咖啡店",
            description: "Alice 对 Bob 发言",
            icon: "💬",
            explanations: [
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
            ],
          },
        ],
      },
    ];

    render(<StoryTimeline chapters={chapters} />);

    expect(
      screen.getByText("High-risk social contact reduced trust and affinity gains."),
    ).toBeInTheDocument();
    expect(screen.getByText("深夜社交风险")).toBeInTheDocument();
  });
});
