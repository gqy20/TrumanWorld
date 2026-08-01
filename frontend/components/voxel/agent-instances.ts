import { VOXEL_MATERIAL_COLORS } from "./materials";
import type { VoxelAgentPlan, VoxelMaterialKey, VoxelVector3 } from "./types";

export type VoxelAgentInstancePart = {
  agentId: string;
  color: number;
  gaitDirection: -1 | 0 | 1;
  key: string;
  position: VoxelVector3;
  size: VoxelVector3;
};

export function buildVoxelAgentInstanceParts(
  agents: VoxelAgentPlan[],
): VoxelAgentInstancePart[] {
  return agents.flatMap((agent) => {
    const { appearance } = agent;
    const heightScale = appearance.heightScale;
    const part = (
      key: string,
      position: [number, number, number],
      size: [number, number, number],
      color: number,
      gaitDirection: VoxelAgentInstancePart["gaitDirection"] = 0,
    ): VoxelAgentInstancePart => ({
      agentId: agent.id,
      color,
      gaitDirection,
      key: `${agent.id}:${key}`,
      position: { x: position[0], y: position[1], z: position[2] },
      size: { x: size[0], y: size[1], z: size[2] },
    });
    const parts = [
      part(
        "torso",
        [0, 0.34 * heightScale, 0],
        [0.22, 0.5 * heightScale, 0.18],
        appearance.torso,
      ),
      part(
        "head",
        [0, 0.67 * heightScale, 0],
        [0.2, 0.2, 0.2],
        appearance.skin,
      ),
      part(
        "hair",
        [0, 0.81 * heightScale, -0.01],
        [0.22, 0.08, 0.22],
        appearance.hair,
      ),
      part(
        "status",
        [0, 0.45 * heightScale, 0.1],
        [0.13, 0.08, 0.025],
        VOXEL_MATERIAL_COLORS[getAgentMaterial(agent.source.status)],
      ),
      part(
        "arm-left",
        [-0.15, 0.39 * heightScale, 0],
        [0.055, 0.34, 0.06],
        appearance.skin,
      ),
      part(
        "arm-right",
        [0.15, 0.39 * heightScale, 0],
        [0.055, 0.34, 0.06],
        appearance.skin,
      ),
      part("leg-left", [-0.07, 0.08, 0], [0.06, 0.16, 0.06], appearance.trousers, 1),
      part(
        "leg-right",
        [0.07, 0.08, 0],
        [0.06, 0.16, 0.06],
        appearance.trousers,
        -1,
      ),
    ];
    if (appearance.accessory === "backpack") {
      parts.push(
        part(
          "backpack",
          [0, 0.4 * heightScale, -0.12],
          [0.19, 0.3, 0.08],
          appearance.accent,
        ),
      );
    }
    if (appearance.accessory === "satchel") {
      parts.push(
        part(
          "satchel",
          [0.15, 0.31 * heightScale, -0.02],
          [0.09, 0.16, 0.08],
          appearance.accent,
        ),
      );
    }
    return parts;
  });
}

function getAgentMaterial(status: VoxelAgentPlan["source"]["status"]): VoxelMaterialKey {
  switch (status) {
    case "moving":
      return "agentMoving";
    case "talking":
      return "agentTalking";
    case "working":
      return "agentWorking";
    case "resting":
      return "agentResting";
    default:
      return "agent";
  }
}
