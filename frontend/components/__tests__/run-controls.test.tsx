import { render, screen } from "@testing-library/react";
import { RunControls } from "@/components/run-controls";
import { useRuns } from "@/components/runs-provider";
import * as api from "@/lib/api";
import type { RunSummary } from "@/lib/types";
import type { ApiResult } from "@/lib/api";

// Mock dependencies
jest.mock("@/components/runs-provider");
jest.mock("@/lib/api");

const mockUseRuns = useRuns as jest.MockedFunction<typeof useRuns>;
const mockPauseRunResult = api.pauseRunResult as jest.MockedFunction<typeof api.pauseRunResult>;
const mockResumeRunResult = api.resumeRunResult as jest.MockedFunction<typeof api.resumeRunResult>;
const mockRestoreAllRunsResult = api.restoreAllRunsResult as jest.MockedFunction<typeof api.restoreAllRunsResult>;

function createMockRun(overrides: Partial<RunSummary> = {}): RunSummary {
  return {
    id: "run-1",
    name: "Test Run",
    status: "running",
    ...overrides,
  };
}

function createMockApiResult<T>(data: T): ApiResult<T> {
  return {
    data,
    error: null,
    status: 200,
  };
}

describe("RunControls", () => {
  const mockRefreshRuns = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    mockUseRuns.mockReturnValue({
      runs: [],
      error: null,
      status: null,
      refreshRuns: mockRefreshRuns,
    });
    mockPauseRunResult.mockResolvedValue(createMockApiResult(createMockRun({ status: "paused" })));
    mockResumeRunResult.mockResolvedValue(createMockApiResult(createMockRun({ status: "running" })));
    mockRestoreAllRunsResult.mockResolvedValue(createMockApiResult([]));
  });

  it("renders nothing when no runs", () => {
    const { container } = render(<RunControls runs={[]} />);

    expect(container.firstChild).toBeNull();
  });

  it("shows running count when there are running runs", () => {
    render(<RunControls runs={[createMockRun({ status: "running" })]} />);

    expect(screen.getByText("1 运行中")).toBeInTheDocument();
  });

  it("shows paused count when there are paused runs", () => {
    render(<RunControls runs={[createMockRun({ status: "paused" })]} />);

    expect(screen.getByText("1 已暂停")).toBeInTheDocument();
  });

  it("shows restore count for runs that need restore", () => {
    render(<RunControls runs={[createMockRun({ status: "stopped", was_running_before_restart: true })]} />);

    expect(screen.getByText("1 待恢复")).toBeInTheDocument();
  });

  it("shows pause button when there are running runs", () => {
    render(<RunControls runs={[createMockRun({ status: "running" })]} />);

    expect(screen.getByRole("button", { name: "全部暂停" })).toBeInTheDocument();
  });

  it("shows resume button when there are paused runs", () => {
    render(<RunControls runs={[createMockRun({ status: "paused" })]} />);

    expect(screen.getByRole("button", { name: "全部开始" })).toBeInTheDocument();
  });

  it("shows resume button when runs need restore", () => {
    render(<RunControls runs={[createMockRun({ status: "stopped", was_running_before_restart: true })]} />);

    expect(screen.getByRole("button", { name: "全部开始" })).toBeInTheDocument();
  });

  it("does not show pause button when no running runs", () => {
    render(<RunControls runs={[createMockRun({ status: "paused" })]} />);

    expect(screen.queryByRole("button", { name: "全部暂停" })).not.toBeInTheDocument();
  });

  it("does not show resume button when no paused or restore-needed runs", () => {
    render(<RunControls runs={[createMockRun({ status: "running" })]} />);

    expect(screen.queryByRole("button", { name: "全部开始" })).not.toBeInTheDocument();
  });
});
