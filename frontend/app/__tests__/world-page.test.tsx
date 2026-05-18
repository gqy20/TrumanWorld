import { fireEvent, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";

import {
  fetchApiResult,
  getDemoAccessStatusResult,
  listScenariosResult,
} from "@/lib/api";
import type { DemoAccessStatus, ScenarioSummary, WorldSnapshot } from "@/lib/types";

import { makeScenarioSummary, makeWorldSnapshot } from "@/test-utils/app/fixtures";
import { errorResult, okResult, renderWorldPage } from "@/test-utils/app/render";

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

jest.mock("@/components/voxel-world-renderer", () => ({
  VoxelWorldRenderer: ({
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

const world = makeWorldSnapshot();

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
        makeScenarioSummary(),
      ]));
    (fetchApiResult as jest.MockedFunction<typeof fetchApiResult>).mockResolvedValue(okResult(world));
  });

  it("renders the world snapshot and opens location and agent flows", async () => {
    renderWorldPage({ initialWorld: world });

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
    renderWorldPage({ initialWorld: world });

    expect(await screen.findByText("当前视图 phaser")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "导演地图" }));

    expect(screen.getByText("当前视图 svg")).toBeInTheDocument();
    expect(screen.getByTestId("town-map")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "SVG Cafe" }));

    expect(await screen.findByText("Location modal cafe")).toBeInTheDocument();
    expect(window.location.search).toBe("?modal=location&loc=cafe");
  });

  it("shows the world load error when the backend is unavailable", async () => {
    (fetchApiResult as jest.MockedFunction<typeof fetchApiResult>)
      .mockResolvedValue(errorResult<WorldSnapshot>("network_error"));

    renderWorldPage({
      initialWorld: null,
    });

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "世界加载失败" })).toBeInTheDocument();
    });
    expect(screen.getByText("后端当前不可达，请确认 API 服务已启动。")).toBeInTheDocument();
  });
});
