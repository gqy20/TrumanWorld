import type { SceneWorld } from "@/lib/world-scene-adapter";

import type { VoxelCameraFocusRequest } from "./camera-controller";

export type VoxelWorldRendererProps = {
  sceneWorld: SceneWorld;
  highlightedLocationId?: string | null;
  highlightedAgentId?: string | null;
  cameraFocusRequest?: VoxelCameraFocusRequest | null;
  onAgentClick?: (agentId: string) => void;
  onLocationClick?: (locationId: string) => void;
};
