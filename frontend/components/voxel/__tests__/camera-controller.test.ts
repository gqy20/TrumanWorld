import {
  VOXEL_CAMERA_MAX_ZOOM,
  VOXEL_CAMERA_MIN_ZOOM,
  calculateVoxelCameraFrame,
  calculateVoxelCameraZoom,
  clampVoxelCameraZoom,
  easeOutQuint,
} from "../camera-controller";
import type { VoxelBounds } from "../types";

const bounds: VoxelBounds = {
  minX: -8,
  maxX: 8,
  minY: -0.4,
  maxY: 2.2,
  minZ: -8,
  maxZ: 8,
};

describe("voxel camera controller", () => {
  it("builds a centered deterministic orthographic frame", () => {
    const frame = calculateVoxelCameraFrame(bounds, { width: 1280, height: 720 });

    expect(frame).toEqual(calculateVoxelCameraFrame(bounds, { width: 1280, height: 720 }));
    expect(frame.aspect).toBeCloseTo(16 / 9);
    expect(frame.target.x).toBe(0);
    expect(frame.target.z).toBe(0);
    expect(frame.position.x).toBeGreaterThan(frame.target.x);
    expect(frame.position.y).toBeGreaterThan(frame.target.y);
    expect(frame.position.z).toBeGreaterThan(frame.target.z);
    expect(frame.viewHeight).toBeGreaterThan(0);
  });

  it("reserves more vertical world space for a portrait viewport", () => {
    const landscape = calculateVoxelCameraFrame(bounds, { width: 1280, height: 720 });
    const portrait = calculateVoxelCameraFrame(bounds, { width: 390, height: 844 });

    expect(portrait.viewHeight).toBeGreaterThan(landscape.viewHeight);
  });

  it("zooms monotonically and clamps extreme wheel input", () => {
    expect(calculateVoxelCameraZoom(1, -120)).toBeGreaterThan(1);
    expect(calculateVoxelCameraZoom(1, 120)).toBeLessThan(1);
    expect(calculateVoxelCameraZoom(1, -100_000)).toBe(VOXEL_CAMERA_MAX_ZOOM);
    expect(calculateVoxelCameraZoom(1, 100_000)).toBe(VOXEL_CAMERA_MIN_ZOOM);
    expect(clampVoxelCameraZoom(Number.POSITIVE_INFINITY)).toBe(VOXEL_CAMERA_MAX_ZOOM);
  });

  it("uses a bounded ease-out curve", () => {
    expect(easeOutQuint(-1)).toBe(0);
    expect(easeOutQuint(0)).toBe(0);
    expect(easeOutQuint(0.5)).toBeGreaterThan(0.5);
    expect(easeOutQuint(1)).toBe(1);
    expect(easeOutQuint(2)).toBe(1);
  });
});
