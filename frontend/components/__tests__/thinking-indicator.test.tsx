import { render } from "@testing-library/react";
import { ThinkingIndicator } from "@/components/thinking-indicator";

// Mock framer-motion
jest.mock("framer-motion", () => ({
  motion: {
    span: ({ children, className }: { children: React.ReactNode; className?: string }) => (
      <span className={className}>{children}</span>
    ),
  },
}));

describe("ThinkingIndicator", () => {
  it("renders three dots", () => {
    const { container } = render(<ThinkingIndicator />);

    const dots = container.querySelectorAll("span.h-2.w-2");
    expect(dots).toHaveLength(3);
  });

  it("applies custom className", () => {
    const { container } = render(<ThinkingIndicator className="custom-class" />);

    expect(container.firstChild).toHaveClass("custom-class");
  });

  it("applies default classes", () => {
    const { container } = render(<ThinkingIndicator />);

    expect(container.firstChild).toHaveClass("flex", "items-center", "gap-1");
  });
});
