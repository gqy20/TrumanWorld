import type { SceneLocation } from "@/lib/world-scene-adapter";

import { buildVoxelPlots, findPlotForLocation } from "../plot-layout";

function location(overrides: Partial<SceneLocation> = {}): SceneLocation {
  const locationType = overrides.locationType ?? "cafe";
  return {
    id: "loc-1",
    name: "Cafe",
    locationType,
    visual: { visualPreset: locationType },
    x: 0,
    y: 0,
    capacity: 6,
    occupantCount: 2,
    heat: 0,
    ...overrides,
  };
}

describe("voxel plot layout", () => {
  it("builds deterministic plots with entrance and agent anchors", () => {
    const plots = buildVoxelPlots([
      location({ id: "office", locationType: "office" }),
      location({ id: "home", locationType: "home" }),
    ]);

    expect(plots.map((plot) => plot.locationId)).toEqual(["home", "office"]);
    expect(plots[0]).toEqual(
      expect.objectContaining({
        locationId: "home",
        district: "home",
        center: { x: -3, z: 3 },
      }),
    );
    expect(plots[0].entrance.z).toBeGreaterThan(plots[0].center.z);
    expect(plots[0].agentAnchors).toHaveLength(6);
  });

  it("spreads duplicate location types away from the base plot", () => {
    const plots = buildVoxelPlots([
      location({ id: "home-a", locationType: "home" }),
      location({ id: "home-b", locationType: "home" }),
    ]);

    expect(plots[0].center).not.toEqual(plots[1].center);
  });

  it("finds plots by location id", () => {
    const plots = buildVoxelPlots([location({ id: "library", locationType: "library" })]);

    expect(findPlotForLocation(plots, "library")?.locationType).toBe("library");
    expect(findPlotForLocation(plots, "missing")).toBeUndefined();
  });

  it("returns one deterministic plot for every location", () => {
    const locations = [
      location({ id: "plaza", locationType: "plaza" }),
      location({ id: "apartment", locationType: "home" }),
      location({ id: "bachelor-apt", locationType: "home" }),
      location({ id: "cafe", locationType: "cafe" }),
    ];

    const first = buildVoxelPlots(locations);
    const second = buildVoxelPlots(locations.slice().reverse());

    expect(first).toHaveLength(locations.length);
    expect(new Set(first.map((plotItem) => plotItem.locationId)).size).toBe(locations.length);
    expect(second.map(({ locationId, center }) => ({ locationId, center })))
      .toEqual(first.map(({ locationId, center }) => ({ locationId, center })));
  });

  it("keeps standard scenario plots from overlapping", () => {
    const narrativeLocations = [
      location({ id: "apartment", locationType: "home" }),
      location({ id: "bachelor-apt", locationType: "home" }),
      location({ id: "cafe", locationType: "cafe" }),
      location({ id: "hospital", locationType: "hospital" }),
      location({ id: "mall", locationType: "shop" }),
      location({ id: "office", locationType: "office" }),
      location({ id: "plaza", locationType: "plaza" }),
    ];
    const campusLocations = [
      location({ id: "cafe", locationType: "cafe" }),
      location({ id: "dorm", locationType: "dorm" }),
      location({ id: "lecture-hall", locationType: "lecture_hall" }),
      location({ id: "library", locationType: "library" }),
      location({ id: "quad", locationType: "quad" }),
    ];

    expect(findOverlappingPlotIds(buildVoxelPlots(narrativeLocations))).toEqual([]);
    expect(findOverlappingPlotIds(buildVoxelPlots(campusLocations))).toEqual([]);
  });
});

function findOverlappingPlotIds(plots: ReturnType<typeof buildVoxelPlots>): string[][] {
  const overlaps: string[][] = [];
  for (let leftIndex = 0; leftIndex < plots.length; leftIndex += 1) {
    for (let rightIndex = leftIndex + 1; rightIndex < plots.length; rightIndex += 1) {
      const left = plots[leftIndex];
      const right = plots[rightIndex];
      const overlapsX = Math.abs(left.center.x - right.center.x)
        < (left.size.width + right.size.width) / 2;
      const overlapsZ = Math.abs(left.center.z - right.center.z)
        < (left.size.depth + right.size.depth) / 2;
      if (overlapsX && overlapsZ) overlaps.push([left.locationId, right.locationId]);
    }
  }
  return overlaps;
}
