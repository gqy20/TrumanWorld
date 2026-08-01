import type { SceneWorld } from "@/lib/world-scene-adapter";

export type VoxelWorldRendererProps = {
  sceneWorld: SceneWorld;
  highlightedLocationId?: string | null;
  highlightedAgentId?: string | null;
  onAgentClick?: (agentId: string) => void;
  onLocationClick?: (locationId: string) => void;
};
