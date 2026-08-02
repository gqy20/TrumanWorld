import {
  advanceVoxelMotionProgress,
  buildVoxelMotionPath,
  calculateVoxelGaitStrength,
  calculateVoxelMotionDuration,
  easeVoxelMotionProgress,
  sampleVoxelMotionPath,
} from "../agent-motion";

describe("voxel agent motion", () => {
  it("samples connected segments by travelled distance instead of segment count", () => {
    const path = buildVoxelMotionPath([
      { x: 0, y: 0, z: 0 },
      { x: 1, y: 0, z: 0 },
      { x: 1, y: 0, z: 3 },
    ]);

    const midpoint = sampleVoxelMotionPath(path, 0.5);
    expect(path.totalLength).toBeCloseTo(3.94, 1);
    expect(midpoint.position.x).toBeCloseTo(1, 2);
    expect(midpoint.position.z).toBeCloseTo(1, 1);
    expect(midpoint.tangent.z).toBeGreaterThan(0.99);
  });

  it("rounds right-angle corners without leaving the road corridor", () => {
    const path = buildVoxelMotionPath([
      { x: 0, y: 0, z: 0 },
      { x: 1, y: 0, z: 0 },
      { x: 1, y: 0, z: 1 },
    ]);

    expect(path.points.length).toBeGreaterThan(3);
    expect(path.points).not.toContainEqual({ x: 1, y: 0, z: 0 });
    expect(path.points.every((point) => point.x >= 0 && point.x <= 1)).toBe(true);
    expect(path.points.every((point) => point.z >= 0 && point.z <= 1)).toBe(true);
  });

  it("accelerates gently and settles the gait at both endpoints", () => {
    expect(easeVoxelMotionProgress(0)).toBe(0);
    expect(easeVoxelMotionProgress(0.25)).toBeLessThan(0.25);
    expect(easeVoxelMotionProgress(0.5)).toBeCloseTo(0.5);
    expect(easeVoxelMotionProgress(0.75)).toBeGreaterThan(0.75);
    expect(easeVoxelMotionProgress(1)).toBe(1);
    expect(calculateVoxelGaitStrength(0)).toBe(0);
    expect(calculateVoxelGaitStrength(0.5)).toBe(1);
    expect(calculateVoxelGaitStrength(1)).toBeCloseTo(0);
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
