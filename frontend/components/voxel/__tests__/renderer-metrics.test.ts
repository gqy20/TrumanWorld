import {
  sampleVoxelRendererMetrics,
  writeVoxelRendererMetrics,
} from "../renderer-metrics";

describe("voxel renderer metrics", () => {
  it("calculates rendered frames per second and preserves WebGL counters", () => {
    expect(
      sampleVoxelRendererMetrics(
        10,
        500,
        { frame: 40, calls: 18, triangles: 960 },
        { geometries: 7, textures: 2 },
      ),
    ).toEqual({
      fps: 60,
      calls: 18,
      triangles: 960,
      geometries: 7,
      textures: 2,
    });
  });

  it("reports an idle demand-rendered scene as zero fps", () => {
    expect(
      sampleVoxelRendererMetrics(
        12,
        1000,
        { frame: 12, calls: 9, triangles: 320 },
        { geometries: 4, textures: 1 },
      ).fps,
    ).toBe(0);
  });

  it("publishes diagnostics as non-visual data attributes", () => {
    const element = document.createElement("div");

    writeVoxelRendererMetrics(element, {
      fps: 58,
      calls: 12,
      triangles: 640,
      geometries: 5,
      textures: 1,
    });

    expect(element.dataset).toEqual(
      expect.objectContaining({
        voxelFps: "58",
        voxelDrawCalls: "12",
        voxelTriangles: "640",
        voxelGeometries: "5",
        voxelTextures: "1",
      }),
    );
  });
});
