import { render, screen, fireEvent } from "@testing-library/react";
import { ErrorState } from "@/components/error-state";

describe("ErrorState", () => {
  it("renders the error message", () => {
    render(<ErrorState message="加载失败" />);

    expect(screen.getByText("加载失败")).toBeInTheDocument();
  });

  it("renders retry button when onRetry is provided", () => {
    const onRetry = jest.fn();
    render(<ErrorState message="出错了" onRetry={onRetry} />);

    const retryButton = screen.getByRole("button", { name: "重试" });
    expect(retryButton).toBeInTheDocument();

    fireEvent.click(retryButton);
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("does not render retry button when onRetry is not provided", () => {
    render(<ErrorState message="出错了" />);

    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("applies small size correctly", () => {
    render(<ErrorState message="小错误" size="sm" />);

    expect(screen.getByText("小错误")).toHaveClass("text-xs");
  });

  it("applies medium size by default", () => {
    render(<ErrorState message="中等错误" />);

    expect(screen.getByText("中等错误")).toHaveClass("text-sm");
  });

  it("applies large size correctly", () => {
    render(<ErrorState message="大错误" size="lg" />);

    expect(screen.getByText("大错误")).toHaveClass("text-base");
  });
});
