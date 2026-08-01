import type { SceneLocation } from "@/lib/world-scene-adapter";

import { buildVoxelPlots } from "../plot-layout";
import { buildRoadGraph, snapRoadPoint } from "../road-graph";
import type { VoxelPlot, VoxelPoint, VoxelRoadTile } from "../types";

function location(id: string, locationType: string): SceneLocation {
  return {
    id,
    name: id,
    locationType,
    visual: { visualPreset: locationType },
    x: 0,
    y: 0,
    capacity: 10,
    occupantCount: 0,
    heat: 0,
  };
}

function narrativePlots(): VoxelPlot[] {
  return buildVoxelPlots([
    location("apartment", "home"),
    location("bachelor-apt", "home"),
    location("cafe", "cafe"),
    location("hospital", "hospital"),
    location("mall", "shop"),
    location("office", "office"),
    location("plaza", "plaza"),
  ]);
}

describe("voxel road graph", () => {
  it("builds one deterministic connected network for all plot entrances", () => {
    const plots = narrativePlots();
    const first = buildRoadGraph(plots);
    const second = buildRoadGraph(plots.slice().reverse());
    const hub = first.find((tile) => tile.role === "plaza");
    const centerPlot = plots.find((plotItem) => plotItem.district === "center");
    if (!centerPlot) throw new Error("Expected a center plot");
    const centerEntrance = snapRoadPoint(centerPlot.entrance);

    expect(second).toEqual(first);
    expect(hub).toBeDefined();
    expect(hub).toEqual(expect.objectContaining(centerEntrance));
    expect(first.filter((tile) => tile.role === "plaza")).toHaveLength(1);
    for (const plotItem of plots) {
      const entrance = snapRoadPoint(plotItem.entrance);
      expect(findTile(first, entrance)).toBeDefined();
      expect(isReachable(first, entrance, hub as VoxelRoadTile)).toBe(true);
    }
  });

  it("keeps every road tile outside building footprints", () => {
    const plots = narrativePlots();
    const roads = buildRoadGraph(plots);

    for (const road of roads) {
      expect(plots.some((plotItem) => isInsideFootprint(road, plotItem))).toBe(false);
    }
  });

  it("emits symmetric connection metadata", () => {
    const roads = buildRoadGraph(narrativePlots());
    const byKey = new Map(roads.map((tile) => [pointKey(tile), tile]));
    const directions = [
      ["north", 0, -1, "south"],
      ["east", 1, 0, "west"],
      ["south", 0, 1, "north"],
      ["west", -1, 0, "east"],
    ] as const;

    for (const tile of roads) {
      for (const [direction, dx, dz, opposite] of directions) {
        const neighbor = byKey.get(pointKey({ x: tile.x + dx, z: tile.z + dz }));
        expect(tile.connections[direction]).toBe(Boolean(neighbor));
        if (neighbor) expect(neighbor.connections[opposite]).toBe(true);
      }
    }
  });

  it("supports the campus layout without disconnected entrances", () => {
    const plots = buildVoxelPlots([
      location("cafe", "cafe"),
      location("dorm", "dorm"),
      location("lecture-hall", "lecture_hall"),
      location("library", "library"),
      location("quad", "quad"),
    ]);
    const roads = buildRoadGraph(plots);
    const hub = roads.find((tile) => tile.role === "plaza");

    expect(hub).toBeDefined();
    for (const plotItem of plots) {
      expect(isReachable(roads, snapRoadPoint(plotItem.entrance), hub as VoxelRoadTile)).toBe(true);
    }
  });
});

function isReachable(roads: VoxelRoadTile[], start: VoxelPoint, goal: VoxelPoint): boolean {
  const roadKeys = new Set(roads.map(pointKey));
  const queue = [start];
  const visited = new Set<string>();
  while (queue.length > 0) {
    const current = queue.shift() as VoxelPoint;
    const key = pointKey(current);
    if (visited.has(key) || !roadKeys.has(key)) continue;
    if (key === pointKey(goal)) return true;
    visited.add(key);
    queue.push(
      { x: current.x, z: current.z - 1 },
      { x: current.x + 1, z: current.z },
      { x: current.x, z: current.z + 1 },
      { x: current.x - 1, z: current.z },
    );
  }
  return false;
}

function findTile(roads: VoxelRoadTile[], point: VoxelPoint): VoxelRoadTile | undefined {
  return roads.find((tile) => tile.x === point.x && tile.z === point.z);
}

function isInsideFootprint(point: VoxelPoint, plotItem: VoxelPlot): boolean {
  return (
    Math.abs(point.x - plotItem.center.x) < plotItem.footprint.width / 2 + 0.05 &&
    Math.abs(point.z - plotItem.center.z) < plotItem.footprint.depth / 2 + 0.05
  );
}

function pointKey(point: VoxelPoint): string {
  return `${point.x}:${point.z}`;
}
