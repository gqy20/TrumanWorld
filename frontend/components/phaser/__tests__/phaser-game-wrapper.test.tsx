import { render, screen, waitFor } from "@testing-library/react";

import type { SceneWorld } from "@/lib/world-scene-adapter";

import { PhaserGameWrapper } from "../phaser-game-wrapper";

const mockGameDestroy = jest.fn();
const mockSceneGet = jest.fn();
const mockSceneEvents = {
  on: jest.fn(),
  off: jest.fn(),
};
const mockSyncWorld = jest.fn();

jest.mock("phaser", () => ({
  Game: jest.fn().mockImplementation(() => ({
    destroy: mockGameDestroy,
    scene: {
      getScene: mockSceneGet,
    },
  })),
  Scene: class MockScene {
    sys = { config: { key: "WorldScene" } };
  },
  AUTO: 0,
  Scale: {
    FIT: 1,
    CENTER_BOTH: 2,
  },
}));

describe("PhaserGameWrapper", () => {
  const sceneWorld: SceneWorld = {
    runId: "run-1",
    locations: [],
    agents: [],
    moveTrails: [],
    bubbles: [],
    ambience: {
      label: "正午",
      overlayColor: "rgba(255, 255, 255, 0.1)",
      isDark: false,
    },
    stage: {},
  };

  beforeEach(() => {
    jest.clearAllMocks();
    mockSceneGet.mockReturnValue({
      syncWorld: mockSyncWorld,
      setHighlightedLocation: jest.fn(),
      setHighlightedAgent: jest.fn(),
      events: mockSceneEvents,
    });
  });

  it("renders the game container", () => {
    render(<PhaserGameWrapper sceneWorld={sceneWorld} />);
    expect(screen.getByTestId("phaser-game-container")).toBeInTheDocument();
  });

  it("creates a Phaser game instance on mount", () => {
    const Phaser = jest.requireMock("phaser");
    render(<PhaserGameWrapper sceneWorld={sceneWorld} />);

    expect(Phaser.Game).toHaveBeenCalledWith(
      expect.objectContaining({
        type: expect.any(Number),
        width: 800,
        height: 600,
        zoom: 1,
      })
    );
  });

  it("pushes scene data into the world scene", async () => {
    const { rerender } = render(<PhaserGameWrapper sceneWorld={sceneWorld} />);

    const nextWorld: SceneWorld = {
      ...sceneWorld,
      agents: [
        {
          id: "agent-1",
          name: "Mei",
          locationId: "loc-1",
          status: "moving",
          slotIndex: 0,
        },
      ],
    };

    rerender(<PhaserGameWrapper sceneWorld={nextWorld} />);

    await waitFor(() => {
      expect(mockSyncWorld).toHaveBeenCalledWith(nextWorld);
    });
  });

  it("destroys the game instance on unmount", () => {
    const { unmount } = render(<PhaserGameWrapper sceneWorld={sceneWorld} />);
    unmount();
    expect(mockGameDestroy).toHaveBeenCalledWith(true);
  });
});
