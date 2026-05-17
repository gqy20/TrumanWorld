import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useEffect } from "react";
import { SWRConfig } from "swr";

import HomePage from "@/app/page";
import { DemoAccessProvider } from "@/components/demo-access-provider";
import { RunsProvider } from "@/components/runs-provider";
import {
  fetchApiResult,
  getDemoAccessStatusResult,
  listScenariosResult,
  type ApiResult,
} from "@/lib/api";
import type { DemoAccessStatus, RunSummary, ScenarioSummary } from "@/lib/types";

const push = jest.fn();

jest.mock("next/navigation", () => ({
  usePathname: () => "/",
  useRouter: () => ({ push }),
}));

jest.mock("@/lib/ui-url-state", () => ({
  useUiSearchParams: () => ({ searchParams: new URLSearchParams() }),
}));

jest.mock("@/components/world-opening-animation", () => ({
  WorldOpeningAnimation: ({
    isVisible,
    onComplete,
  }: {
    isVisible: boolean;
    onComplete: () => void;
  }) => {
    useEffect(() => {
      if (isVisible) {
        onComplete();
      }
    }, [isVisible, onComplete]);

    return null;
  },
}));

jest.mock("@/lib/api", () => {
  const actual = jest.requireActual("@/lib/api");

  return {
    ...actual,
    fetchApiResult: jest.fn(),
    getDemoAccessStatusResult: jest.fn(),
    listScenariosResult: jest.fn(),
  };
});

function okResult<T>(data: T, status = 200): ApiResult<T> {
  return {
    data,
    error: null,
    errorCode: null,
    errorDetail: null,
    status,
  };
}

function errorResult<T>(error: string, status: number | null = null): ApiResult<T> {
  return {
    data: null,
    error,
    errorCode: null,
    errorDetail: null,
    status,
  };
}

const scenarios: ScenarioSummary[] = [
  { id: "narrative_world", name: "Narrative World", version: 1 },
  { id: "open_world", name: "Open World", version: 1 },
];

const runs: RunSummary[] = [
  {
    id: "run-alpha",
    name: "Campus Morning",
    status: "running",
    scenario_type: "narrative_world",
    current_tick: 12,
    agent_count: 3,
    location_count: 2,
    event_count: 5,
    created_at: "2026-03-02T06:00:00Z",
  },
  {
    id: "run-beta",
    name: "Paused Town",
    status: "paused",
    scenario_type: "open_world",
    current_tick: 4,
    agent_count: 1,
    location_count: 1,
    event_count: 0,
    created_at: "2026-03-02T07:00:00Z",
  },
];

function renderHome(initialResult: ApiResult<RunSummary[]>) {
  return render(
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
      <DemoAccessProvider>
        <RunsProvider initialResult={initialResult}>
          <HomePage />
        </RunsProvider>
      </DemoAccessProvider>
    </SWRConfig>,
  );
}

describe("HomePage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    window.sessionStorage.clear();
    window.requestAnimationFrame = (callback: FrameRequestCallback) => {
      callback(0);
      return 0;
    };

    (getDemoAccessStatusResult as jest.MockedFunction<typeof getDemoAccessStatusResult>)
      .mockResolvedValue(okResult<DemoAccessStatus>({
        write_protected: false,
        admin_authorized: false,
      }));
    (listScenariosResult as jest.MockedFunction<typeof listScenariosResult>)
      .mockResolvedValue(okResult(scenarios));
    (fetchApiResult as jest.MockedFunction<typeof fetchApiResult>)
      .mockResolvedValue(okResult(runs));
  });

  it("renders seeded runs and navigates to the selected world", async () => {
    renderHome(okResult(runs));

    expect(await screen.findByRole("heading", { name: "Truman World" })).toBeInTheDocument();
    expect(screen.getByText("1 个运行中")).toBeInTheDocument();
    expect(screen.getByText("Campus Morning")).toBeInTheDocument();
    expect(screen.getByText("Paused Town")).toBeInTheDocument();
    expect(screen.getAllByText("Narrative World").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Open World").length).toBeGreaterThan(0);
    expect(screen.getByText("运行中")).toBeInTheDocument();
    expect(screen.getByText("已暂停")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Campus Morning/ }));

    await waitFor(() => {
      expect(push).toHaveBeenCalledWith("/runs/run-alpha/world");
    });
  });

  it("shows the network error and empty state when the initial run load fails", async () => {
    (fetchApiResult as jest.MockedFunction<typeof fetchApiResult>)
      .mockResolvedValue(errorResult<RunSummary[]>("network_error"));

    renderHome(errorResult<RunSummary[]>("network_error"));

    expect(await screen.findByText("后端当前不可达，列表展示的是空状态。"))
      .toBeInTheDocument();
    expect(screen.getByText("还没有运行")).toBeInTheDocument();
    expect(screen.getByText("在上方创建第一个模拟运行")).toBeInTheDocument();
  });
});
