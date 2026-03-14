import { render, screen, act } from "@testing-library/react";
import { TypewriterText } from "@/components/typewriter-text";

// Mock framer-motion
jest.mock("framer-motion", () => ({
  motion: {
    span: ({ children, className }: { children: React.ReactNode; className?: string }) => (
      <span className={className}>{children}</span>
    ),
  },
}));

describe("TypewriterText", () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it("starts with empty text when animating", () => {
    const { container } = render(<TypewriterText text="Hello" speed={10} />);

    // Initially displayedChars is 0, so text is empty
    expect(container.textContent).toBe("");
  });

  it("displays text progressively over time", () => {
    const { container } = render(<TypewriterText text="Hello" speed={10} />);

    act(() => {
      jest.advanceTimersByTime(25);
    });

    // Should show some characters now
    expect(container.textContent?.length).toBeGreaterThan(0);
    expect(container.textContent?.length).toBeLessThan(6);
  });

  it("displays full text immediately when not animating", () => {
    render(<TypewriterText text="Hello" isAnimating={false} />);

    expect(screen.getByText("Hello")).toBeInTheDocument();
  });

  it("applies custom className", () => {
    const { container } = render(<TypewriterText text="Test" className="custom-class" />);

    expect(container.querySelector(".custom-class")).toBeInTheDocument();
  });

  it("shows cursor while typing", () => {
    const { container } = render(<TypewriterText text="Test" speed={100} />);

    // Cursor should be visible when text is not complete
    const cursor = container.querySelector(".bg-current");
    expect(cursor).toBeInTheDocument();
  });
});
