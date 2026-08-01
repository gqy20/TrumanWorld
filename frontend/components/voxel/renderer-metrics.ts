import type * as THREE from "three";

export type VoxelRendererMetrics = {
  fps: number;
  calls: number;
  triangles: number;
  geometries: number;
  textures: number;
};

export type VoxelRendererCounter = {
  frame: number;
  calls: number;
  triangles: number;
};

export function sampleVoxelRendererMetrics(
  previousFrame: number,
  elapsedMs: number,
  render: VoxelRendererCounter,
  memory: Pick<THREE.WebGLInfo["memory"], "geometries" | "textures">,
): VoxelRendererMetrics {
  const renderedFrames = Math.max(0, render.frame - previousFrame);
  return {
    fps: elapsedMs > 0 ? Math.round((renderedFrames * 1000) / elapsedMs) : 0,
    calls: render.calls,
    triangles: render.triangles,
    geometries: memory.geometries,
    textures: memory.textures,
  };
}

export function writeVoxelRendererMetrics(
  element: HTMLElement,
  metrics: VoxelRendererMetrics,
): void {
  element.dataset.voxelFps = String(metrics.fps);
  element.dataset.voxelDrawCalls = String(metrics.calls);
  element.dataset.voxelTriangles = String(metrics.triangles);
  element.dataset.voxelGeometries = String(metrics.geometries);
  element.dataset.voxelTextures = String(metrics.textures);
}
