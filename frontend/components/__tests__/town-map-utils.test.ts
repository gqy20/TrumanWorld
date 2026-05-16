import { EVENT_MOVE } from "@/lib/simulation-protocol";
import type { WorldSnapshot } from "@/lib/types";

import {
  SVG_H,
  SVG_W,
  agentColor,
  buildMapData,
  clampViewBox,
  scaleCoordinate,
} from "../town-map-utils";

function makeWorld(): WorldSnapshot {
  return {
    run: { id: "run-1", name: "Demo", status: "running" },
    locations: [
      {
        id: "home",
        name: "Home",
        location_type: "home",
        x: 0,
        y: 0,
        capacity: 4,
        occupants: [{ id: "agent-1", name: "Mei" }],
      },
      {
        id: "plaza",
        name: "Plaza",
        location_type: "plaza",
        x: 5,
        y: 5,
        capacity: 8,
        occupants: [],
      },
      {
        id: "office",
        name: "Office",
        location_type: "office",
        x: 10,
        y: 10,
        capacity: 6,
        occupants: [],
      },
    ],
    recent_events: [
      {
        id: "move-1",
        tick_no: 1,
        event_type: EVENT_MOVE,
        location_id: "home",
        payload: { to_location_id: "office" },
      },
    ],
  };
}

describe("town map helpers", () => {
  it("scales equal coordinates to the canvas center", () => {
    expect(scaleCoordinate(5, 5, 5, SVG_W)).toBe(SVG_W / 2);
    expect(scaleCoordinate(5, 5, 5, SVG_H)).toBe(SVG_H / 2);
  });

  it("clamps view boxes while preserving the canvas aspect ratio", () => {
    const viewBox = clampViewBox({ x: -1000, y: -1000, width: 100, height: 10 });

    expect(viewBox.x).toBe(200);
    expect(viewBox.y).toBeCloseTo(125.714);
    expect(viewBox.width).toBe(300);
    expect(viewBox.height).toBeCloseTo(188.571);
  });

  it("builds nodes, links, move paths, and decorative paths from a world snapshot", () => {
    const mapData = buildMapData(makeWorld());

    expect(mapData.nodes).toHaveLength(3);
    expect(mapData.nodes[0]).toMatchObject({
      id: "home",
      occupantCount: 1,
      svgX: 88,
      svgY: 88,
    });
    expect(mapData.links.length).toBeGreaterThan(0);
    expect(mapData.movePaths).toEqual([
      {
        id: "move-1",
        fromX: 88,
        fromY: 88,
        toX: 612,
        toY: 352,
      },
    ]);
    expect(mapData.mainRoadPath).toContain("Q");
    expect(mapData.coastPath).toContain("C");
  });

  it("assigns stable colors for agent ids", () => {
    expect(agentColor("agent-1")).toBe(agentColor("agent-1"));
    expect(agentColor("agent-1")).toMatch(/^#[0-9a-f]{6}$/);
  });
});
