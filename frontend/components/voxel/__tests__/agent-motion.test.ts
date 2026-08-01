import {
  advanceVoxelMotionProgress,
  buildVoxelMotionPath,
  calculateVoxelMotionDuration,
  sampleVoxelMotionPath,
} from "../agent-motion";

describe("voxel agent motion", () => {
  it("samples connected segments by travelled distance instead of segment count", () => {
    const path = buildVoxelMotionPath([
      { x: 0, y: 0, z: 0 },
      { x: 1, y: 0, z: 0 },
      { x: 1, y: 0, z: 3 },
    ]);

    expect(path.totalLength).toBe(4);
    expect(sampleVoxelMotionPath(path, 0.5)).toEqual({
      position: { x: 1, y: 0, z: 1 },
      tangent: { x: 0, y: 0, z: 1 },
    });
  });

  it("deduplicates adjacent points and clamps samples to the path endpoints", () => {
    const path = buildVoxelMotionPath([
      { x: 2, y: 0, z: 1 },
      { x: 2, y: 0, z: 1 },
      { x: 4, y: 0, z: 1 },
    ]);

    expect(path.points).toHaveLength(2);
    expect(sampleVoxelMotionPath(path, -1).position).toEqual({ x: 2, y: 0, z: 1 });
    expect(sampleVoxelMotionPath(path, 2).position).toEqual({ x: 4, y: 0, z: 1 });
  });

  it("keeps short and long routes inside the stage motion budget", () => {
    expect(calculateVoxelMotionDuration(0.1)).toBe(900);
    expect(calculateVoxelMotionDuration(100)).toBe(4800);
    expect(calculateVoxelMotionDuration(4.4)).toBe(2000);
  });

  it("freezes progress while paused and resumes from the same pixel", () => {
    expect(advanceVoxelMotionProgress(0.35, 2000, 0.5, true)).toBe(0.35);
    expect(advanceVoxelMotionProgress(0.35, 2000, 0.5, false)).toBe(0.6);
    expect(advanceVoxelMotionProgress(0.9, 1000, 0.5, false)).toBe(1);
  });
});
