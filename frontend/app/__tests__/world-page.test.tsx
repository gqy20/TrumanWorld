import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { SWRConfig } from "swr";

import WorldPage from "@/app/runs/[runId]/world/page";
import { DemoAccessProvider } from "@/components/demo-access-provider";
import { WorldProvider } from "@/components/world-context";
import {
  fetchApiResult,
  getDemoAccessStatusResult,
  listScenariosResult,
  type ApiResult,
} from "@/lib/api";
import type {
  DemoAccessStatus,
  RunSummary,
  ScenarioSummary,
  WorldSnapshot,
} from "@/lib/types";

jest.mock("framer-motion", () => {
  const React = jest.requireActual("react");
  const AnimatePresence = ({ children }: { children?: ReactNode }) => <>{children}</>;

  return {
    AnimatePresence,
    motion: new Proxy(
      {},
      {
        get: (_target, tag: string) =>
          ({
            animate: _animate,
            exit: _exit,
            initial: _initial,
            transition: _transition,
            whileHover: _whileHover,
            whileTap: _whileTap,
            children,
            ...props
          }: {
            animate?: unknown;
            exit?: unknown;
            initial?: unknown;
            transition?: unknown;
            whileHover?: unknown;
            whileTap?: unknown;
            children?: ReactNode;
          }) => React.createElement(tag, props, children),
      },
    ),
  };
});

jest.mock("@/components/agent-avatar", () => ({
  AgentAvatar: ({ name }: { name: string }) => <span aria-hidden="true">{name.slice(0, 1)}</span>,
}));

jest.mock("@/components/phaser", () => ({
  PhaserGameWrapper: ({
    onAgentClick,
    onLocationClick,
  }: {
    onAgentClick?: (agentId: string) => void;
    onLocationClick?: (locationId: string) => void;
  }) => (
    <div data-testid="phaser-game-container">
      <button type="button" onClick={() => onLocationClick?.("library")}>
        Phaser Library
      </button>
      <button type="button" onClick={() => onAgentClick?.("agent-1")}>
        Phaser Mei
      </button>
    </div>
  ),
  ViewToggleButton: ({
    currentView,
    onToggle,
  }: {
    currentView: "svg" | "phaser";
    onToggle: (view: "svg" | "phaser") => void;
  }) => (
    <div>
      <span>当前视图 {currentView}</span>
      <button type="button" onClick={() => onToggle("svg")}>
        导演地图
      </button>
      <button type="button" onClick={() => onToggle("phaser")}>
        舞台视图
      </button>
    </div>
  ),
}));

jest.mock("@/components/town-map", () => ({
  TownMap: ({
    onAgentClick,
    onLocationClick,
  }: {
    onAgentClick?: (agentId: string) => void;
    onLocationClick?: (locationId: string) => void;
  }) => (
    <div data-testid="town-map">
      <button type="button" onClick={() => onLocationClick?.("cafe")}>
        SVG Cafe
      </button>
      <button type="button" onClick={() => onAgentClick?.("agent-1")}>
        SVG Mei
      </button>
    </div>
  ),
}));

jest.mock("@/components/location-detail-modal", () => ({
  LocationDetailModal: ({ isOpen, locationId }: { isOpen: boolean; locationId: string }) =>
    isOpen ? <div role="dialog">Location modal {locationId}</div> : null,
}));

jest.mock("@/components/agent-detail-modal", () => ({
  AgentDetailModal: ({ isOpen, agentId }: { isOpen: boolean; agentId: string }) =>
    isOpen ? <div role="dialog">Agent modal {agentId}</div> : null,
}));

jest.mock("@/components/timeline-modal", () => ({
  TimelineModal: ({ isOpen }: { isOpen: boolean }) =>
    isOpen ? <div role="dialog">Timeline modal</div> : null,
}));

jest.mock("@/components/intelligence-stream-modal", () => ({
  IntelligenceStreamModal: ({ isOpen }: { isOpen: boolean }) =>
    isOpen ? <div role="dialog">Stream modal</div> : null,
}));

jest.mock("@/components/world-health-director", () => ({
  DirectorInterventionModal: ({ isOpen }: { isOpen: boolean }) =>
    isOpen ? <div role="dialog">Director modal</div> : null,
  DirectorStats: () => <button type="button">导演干预</button>,
}));

jest.mock("@/components/world-health-system", () => ({
  SystemStatusModal: ({ isOpen }: { isOpen: boolean }) =>
    isOpen ? <div role="dialog">System modal</div> : null,
  SystemStatusPanel: () => <button type="button">系统状态</button>,
}));

jest.mock("@/lib/api", () => {
  const actual = jest.requireActual("@/lib/api");

  return {
    ...actual,
    fetchApiResult: jest.fn(),
    getDemoAccessStatusResult: jest.fn(),
    getSystemMetrics: jest.fn().mockResolvedValue(null),
    getSystemOverview: jest.fn().mockResolvedValue(null),
    getWorldPulseResult: jest.fn(),
    listScenariosResult: jest.fn(),
    pauseRunResult: jest.fn(),
    startRunResult: jest.fn(),
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

const run: RunSummary = {
  id: "run-1",
  name: "Campus Morning",
  status: "running",
  scenario_type: "narrative_world",
  current_tick: 24,
  tick_minutes: 5,
  agent_count: 1,
  location_count: 2,
  event_count: 2,
  elapsed_seconds: 120,
  started_at: "2026-03-02T06:00:00Z",
};

const world: WorldSnapshot = {
  run,
  world_clock: {
    iso: "2026-03-02T08:00:00Z",
    date: "2026-03-02",
    time: "08:00",
    year: 2026,
    month: 3,
    day: 2,
    hour: 8,
    minute: 0,
    weekday: 1,
    weekday_name: "Monday",
    weekday_name_cn: "周一",
    is_weekend: false,
    time_period: "morning",
    time_period_cn: "上午",
  },
  subject_agent_id: "agent-1",
  locations: [
    {
      id: "cafe",
      name: "Cafe",
      location_type: "cafe",
      x: 10,
      y: 20,
      capacity: 6,
      occupants: [
        {
          id: "agent-1",
          name: "Mei Lin",
          occupation: "Student",
          current_goal: "talk",
          current_location_id: "cafe",
          status: { alert_score: 0.2 },
        },
      ],
    },
    {
      id: "library",
      name: "Library",
      location_type: "library",
      x: 30,
      y: 40,
      capacity: 8,
      occupants: [],
    },
  ],
  recent_events: [
    {
      id: "event-1",
      tick_no: 24,
      event_type: "talk",
      location_id: "cafe",
      actor_agent_id: "agent-1",
      actor_name: "Mei Lin",
      payload: { message: "Good morning" },
    },
    {
      id: "event-2",
      tick_no: 23,
      event_type: "move",
      location_id: "cafe",
      actor_agent_id: "agent-1",
      actor_name: "Mei Lin",
      payload: { from_location_id: "library", to_location_id: "cafe" },
    },
  ],
  director_stats: {
    total: 2,
    executed: 1,
    execution_rate: 0.5,
  },
  daily_stats: {
    talk_count: 4,
    move_count: 2,
    rejection_count: 0,
    total_input_tokens: 1000,
    total_output_tokens: 500,
    total_reasoning_tokens: 0,
    total_cache_read_tokens: 0,
    total_cache_creation_tokens: 0,
  },
};

function renderWorldPage({
  initialWorld = world,
  fetchResult = okResult(world),
}: {
  initialWorld?: WorldSnapshot | null;
  fetchResult?: ApiResult<WorldSnapshot>;
} = {}) {
  window.history.replaceState(null, "", "/runs/run-1/world");
  (fetchApiResult as jest.MockedFunction<typeof fetchApiResult>).mockResolvedValue(fetchResult);

  return render(
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
      <DemoAccessProvider>
        <WorldProvider runId="run-1" initialData={initialWorld}>
          <WorldPage />
        </WorldProvider>
      </DemoAccessProvider>
    </SWRConfig>,
  );
}

describe("WorldPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    window.sessionStorage.clear();
    (getDemoAccessStatusResult as jest.MockedFunction<typeof getDemoAccessStatusResult>)
      .mockResolvedValue(okResult<DemoAccessStatus>({
        write_protected: false,
        admin_authorized: false,
      }));
    (listScenariosResult as jest.MockedFunction<typeof listScenariosResult>)
      .mockResolvedValue(okResult<ScenarioSummary[]>([
        { id: "narrative_world", name: "Narrative World", version: 1 },
      ]));
  });

  it("renders the world snapshot and opens location and agent flows", async () => {
    renderWorldPage();

    expect(await screen.findByRole("heading", { name: "Campus Morning" })).toBeInTheDocument();
    expect(screen.getByText("Narrative World")).toBeInTheDocument();
    expect(screen.getByText("第1天 周一 08:00")).toBeInTheDocument();
    expect(screen.getByText("时间步 24")).toBeInTheDocument();
    expect(screen.getByTestId("phaser-game-container")).toBeInTheDocument();
    expect(screen.getAllByText("Cafe").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Mei Lin").length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "Phaser Library" }));

    expect(await screen.findByText("Location modal library")).toBeInTheDocument();
    expect(window.location.search).toBe("?modal=location&loc=library");

    fireEvent.click(screen.getByRole("button", { name: "Phaser Mei" }));

    expect(await screen.findByText("Agent modal agent-1")).toBeInTheDocument();
    expect(window.location.search).toBe("?modal=agent&loc=library&agent=agent-1");
  });

  it("switches from Phaser to SVG renderer and keeps SVG click flows wired", async () => {
    renderWorldPage();

    expect(await screen.findByText("当前视图 phaser")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "导演地图" }));

    expect(screen.getByText("当前视图 svg")).toBeInTheDocument();
    expect(screen.getByTestId("town-map")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "SVG Cafe" }));

    expect(await screen.findByText("Location modal cafe")).toBeInTheDocument();
    expect(window.location.search).toBe("?modal=location&loc=cafe");
  });

  it("shows the world load error when the backend is unavailable", async () => {
    renderWorldPage({
      initialWorld: null,
      fetchResult: errorResult<WorldSnapshot>("network_error"),
    });

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "世界加载失败" })).toBeInTheDocument();
    });
    expect(screen.getByText("后端当前不可达，请确认 API 服务已启动。")).toBeInTheDocument();
  });
});
