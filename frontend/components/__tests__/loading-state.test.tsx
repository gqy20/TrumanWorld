import { render, screen } from "@testing-library/react";
import { LoadingState } from "@/components/loading-state";

describe("LoadingState", () => {
  it("renders default message", () => {
    render(<LoadingState />);

    expect(screen.getByText("加载中...")).toBeInTheDocument();
  });

  it("renders custom message", () => {
    render(<LoadingState message="正在获取数据" />);

    expect(screen.getByText("正在获取数据")).toBeInTheDocument();
  });

  it("renders spinner svg", () => {
    const { container } = render(<LoadingState />);

    const svg = container.querySelector("svg");
    expect(svg).toBeInTheDocument();
    expect(svg).toHaveClass("animate-spin");
  });

  it("applies small size correctly", () => {
    const { container } = render(<LoadingState size="sm" />);

    const svg = container.querySelector("svg");
    expect(svg).toHaveClass("h-8", "w-8");

    expect(screen.getByText("加载中...")).toHaveClass("text-xs");
  });

  it("applies medium size by default", () => {
    const { container } = render(<LoadingState />);

    const svg = container.querySelector("svg");
    expect(svg).toHaveClass("h-12", "w-12");

    expect(screen.getByText("加载中...")).toHaveClass("text-sm");
  });

  it("applies large size correctly", () => {
    const { container } = render(<LoadingState size="lg" />);

    const svg = container.querySelector("svg");
    expect(svg).toHaveClass("h-16", "w-16");

    expect(screen.getByText("加载中...")).toHaveClass("text-base");
  });
});
