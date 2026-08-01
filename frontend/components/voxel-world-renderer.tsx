"use client";

import dynamic from "next/dynamic";

import type { VoxelWorldRendererProps } from "@/components/voxel/renderer-types";

const VoxelCanvas = dynamic(
  () => import("@/components/voxel/voxel-canvas").then((module) => module.VoxelCanvas),
  {
    ssr: false,
    loading: () => (
      <div
        data-testid="voxel-stage-loading"
        className="flex h-full min-h-[420px] items-center justify-center rounded-2xl border border-emerald-100 bg-[#eef5e8] text-sm text-slate-500"
      >
        正在加载世界舞台…
      </div>
    ),
  },
);

export function VoxelWorldRenderer(props: VoxelWorldRendererProps) {
  return <VoxelCanvas {...props} />;
}

export type { VoxelWorldRendererProps } from "@/components/voxel/renderer-types";
