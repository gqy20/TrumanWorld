import {
  focusCameraOnSelection,
  hideTooltip,
  playTapFeedback,
  refreshAgentHighlights,
  refreshLocationHighlights,
  showTooltip,
  type TooltipNode,
} from "../world-scene-interactions";
import { CANVAS_HEIGHT, CANVAS_WIDTH } from "../world-scene-style";
import type { AgentNode, LocationNode } from "../world-scene-sync";

function gameObject(overrides: Record<string, unknown> = {}) {
  return {
    alpha: 0.12,
    x: 0,
    y: 0,
    clearTint: jest.fn(),
    setAlpha: jest.fn(),
    setPosition: jest.fn(),
    setScale: jest.fn(),
    setSize: jest.fn(),
    setText: jest.fn(),
    setTint: jest.fn(),
    setVisible: jest.fn(),
    ...overrides,
  };
}

function locationNode(overrides: Partial<LocationNode> = {}): LocationNode {
  return {
    body: gameObject({ x: 120, y: 140 }),
    glow: gameObject({ alpha: 0.16 }),
    icon: gameObject(),
    label: gameObject(),
    badge: gameObject(),
    ...overrides,
  } as unknown as LocationNode;
}

function agentNode(overrides: Partial<AgentNode> = {}): AgentNode {
  return {
    body: gameObject({ x: 240, y: 260 }),
    marker: gameObject(),
    label: gameObject(),
    shadow: gameObject(),
    ...overrides,
  } as unknown as AgentNode;
}

describe("world scene interaction helpers", () => {
  it("refreshes location highlight state", () => {
    const highlighted = locationNode();
    const normal = locationNode();
    const nodes = new Map([
      ["highlighted", highlighted],
      ["normal", normal],
    ]);

    refreshLocationHighlights(nodes, "highlighted");

    expect(highlighted.body.setTint).toHaveBeenCalledWith(0xf8fafc);
    expect(highlighted.body.setScale).toHaveBeenCalledWith(1.06);
    expect(highlighted.icon.setAlpha).toHaveBeenCalledWith(0.95);
    expect(highlighted.label.setAlpha).toHaveBeenCalledWith(1);
    expect(highlighted.badge.setAlpha).toHaveBeenCalledWith(1);
    expect(highlighted.label.setScale).toHaveBeenCalledWith(1.05);
    expect(highlighted.badge.setScale).toHaveBeenCalledWith(1.05);
    expect(highlighted.glow.setAlpha).toHaveBeenCalledWith(0.34);
    expect(normal.body.clearTint).toHaveBeenCalled();
    expect(normal.body.setScale).toHaveBeenCalledWith(1);
    expect(normal.icon.setAlpha).toHaveBeenCalledWith(0.42);
    expect(normal.label.setAlpha).toHaveBeenCalledWith(0);
    expect(normal.badge.setAlpha).toHaveBeenCalledWith(0);
  });

  it("refreshes agent highlight state and stops stale tweens", () => {
    const staleTween = { stop: jest.fn() };
    const highlighted = agentNode();
    const normal = agentNode({ pulseTween: staleTween as never });
    const scene = {
      tweens: {
        add: jest.fn(() => ({ stop: jest.fn() })),
      },
    };

    refreshAgentHighlights(
      scene as never,
      new Map([
        ["highlighted", highlighted],
        ["normal", normal],
      ]),
      "highlighted"
    );

    expect(highlighted.body.setTint).toHaveBeenCalledWith(0xfef08a);
    expect(highlighted.marker.setAlpha).toHaveBeenCalledWith(0.95);
    expect(highlighted.marker.setScale).toHaveBeenCalledWith(1.08);
    expect(highlighted.label.setAlpha).toHaveBeenCalledWith(1);
    expect(scene.tweens.add).toHaveBeenCalledWith(
      expect.objectContaining({
        targets: [highlighted.body, highlighted.marker, highlighted.label],
        repeat: -1,
      })
    );
    expect(staleTween.stop).toHaveBeenCalled();
    expect(normal.body.clearTint).toHaveBeenCalled();
    expect(normal.marker.setAlpha).toHaveBeenCalledWith(0);
    expect(normal.label.setAlpha).toHaveBeenCalledWith(0);
    expect(normal.pulseTween).toBeUndefined();
  });

  it("focuses camera on agent, location, then canvas center", () => {
    const camera = { pan: jest.fn() };
    const locations = new Map([["loc-1", locationNode()]]);
    const agents = new Map([["agent-1", agentNode()]]);

    focusCameraOnSelection(camera as never, locations, agents, "loc-1", "agent-1");
    expect(camera.pan).toHaveBeenLastCalledWith(240, 260, 320, "Sine.easeInOut", true);

    focusCameraOnSelection(camera as never, locations, agents, "loc-1", null);
    expect(camera.pan).toHaveBeenLastCalledWith(120, 140, 320, "Sine.easeInOut", true);

    focusCameraOnSelection(camera as never, locations, agents, null, null);
    expect(camera.pan).toHaveBeenLastCalledWith(
      CANVAS_WIDTH / 2,
      CANVAS_HEIGHT / 2,
      320,
      "Sine.easeInOut",
      true
    );
  });

  it("shows, hides, and animates interaction feedback", () => {
    const tooltip: TooltipNode = {
      box: gameObject() as never,
      text: gameObject() as never,
    };
    const scene = {
      tweens: {
        add: jest.fn(),
      },
    };
    const target = gameObject();

    showTooltip(tooltip, 12, 24, "Cafe");
    expect(tooltip.box.setPosition).toHaveBeenCalledWith(12, 24);
    expect(tooltip.box.setSize).toHaveBeenCalledWith(120, 30);
    expect(tooltip.text.setText).toHaveBeenCalledWith("Cafe");
    expect(tooltip.text.setVisible).toHaveBeenCalledWith(true);

    hideTooltip(tooltip);
    expect(tooltip.box.setVisible).toHaveBeenCalledWith(false);
    expect(tooltip.text.setVisible).toHaveBeenCalledWith(false);

    playTapFeedback(scene as never, target as never);
    expect(scene.tweens.add).toHaveBeenCalledWith(
      expect.objectContaining({
        targets: [target],
        duration: 110,
      })
    );
  });
});
