import type { SceneLocation } from "@/lib/world-scene-adapter";

import { buildLocationPrefab, resolvePrefabKind } from "../prefabs";
import type { VoxelPlot, VoxelPrefab } from "../types";

describe("voxel location prefabs", () => {
  it.each([
    ["house", "home", "home"],
    ["shop", "cafe", "cafe"],
    ["tower", "office", "office"],
    ["hall", "library", "library"],
    ["clinic", "hospital", "hospital"],
    ["square", "plaza", "plaza"],
    ["grove", "park", "green"],
    ["unknown", "unknown", "generic"],
  ] as const)("maps %s/%s to the %s prefab", (visualPreset, locationType, expected) => {
    expect(resolvePrefabKind(visualPreset, locationType)).toBe(expected);
  });

  it("builds deterministic, valid and visually distinct silhouettes", () => {
    const kinds: Array<VoxelPrefab["kind"]> = [
      "home",
      "cafe",
      "office",
      "library",
      "hospital",
      "plaza",
      "green",
      "generic",
    ];
    const signatures = kinds.map((kind) => {
      const plot = makePlot(kind);
      const first = buildLocationPrefab(plot.source, plot);
      const second = buildLocationPrefab(plot.source, plot);

      expect(second).toEqual(first);
      expect(first.kind).toBe(kind);
      expect(first.blocks.length).toBeGreaterThan(0);
      expect(
        first.blocks.every((block) => Object.values(block.size).every((size) => size > 0)),
      ).toBe(true);

      return [
        first.blocks.length,
        Math.max(...first.blocks.map((block) => block.position.y + block.size.y / 2)),
        [...new Set(first.blocks.map((block) => block.material))].sort().join(","),
      ].join(":");
    });

    expect(new Set(signatures).size).toBe(kinds.length);
  });

  it("models a plaza as public space instead of a generic building", () => {
    const plot = makePlot("plaza");
    const prefab = buildLocationPrefab(plot.source, plot);
    const materials = prefab.blocks.map((block) => block.material);

    expect(materials).toEqual(expect.arrayContaining(["paving", "water", "wallStone", "wood"]));
    expect(materials).not.toContain("wallWarm");
    expect(materials).not.toContain("wallCool");
  });

  it("rotates the facade toward the configured plot entrance", () => {
    const plot = makePlot("office", "west");
    const prefab = buildLocationPrefab(plot.source, plot);
    const door = prefab.blocks.find(
      (block) => block.material === "wood" && block.size.y === 0.68,
    );
    if (!door) throw new Error("Expected office prefab to expose a front door");

    const entranceDirection = {
      x: plot.entrance.x - plot.center.x,
      z: plot.entrance.z - plot.center.z,
    };
    const facadeDirection = { x: door.position.x, z: door.position.z };
    const dot =
      entranceDirection.x * facadeDirection.x + entranceDirection.z * facadeDirection.z;

    expect(dot).toBeGreaterThan(0);
    expect(prefab.blocks.every((block) => block.rotationY === -Math.PI / 2)).toBe(true);
  });
});

function makePlot(
  kind: VoxelPrefab["kind"],
  entranceSide: "north" | "east" | "south" | "west" = "south",
): VoxelPlot {
  const locationType = kind === "green" ? "park" : kind;
  const source: SceneLocation = {
    id: `location-${kind}`,
    name: kind,
    locationType,
    visual: { visualPreset: kind },
    x: 0,
    y: 0,
    capacity: 10,
    occupantCount: 0,
    heat: 0,
  };
  const center = { x: 0, z: 0 };
  const entranceBySide = {
    north: { x: 0, z: -1.65 },
    east: { x: 1.65, z: 0 },
    south: { x: 0, z: 1.65 },
    west: { x: -1.65, z: 0 },
  };

  return {
    id: `plot-${kind}`,
    locationId: source.id,
    locationType,
    district: kind === "plaza" ? "center" : kind === "green" ? "green" : "civic",
    center,
    size: { width: 2.8, depth: 2.8 },
    footprint: { width: 1.5, depth: 1.4 },
    entrance: entranceBySide[entranceSide],
    agentAnchors: [],
    decorationAnchors: [],
    source,
  };
}
