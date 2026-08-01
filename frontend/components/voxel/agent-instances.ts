import { VOXEL_MATERIAL_COLORS } from "./materials";
import type { VoxelAgentPlan, VoxelMaterialKey, VoxelVector3 } from "./types";

export type VoxelAgentInstancePart = {
  agentId: string;
  color: number;
  gaitDirection: -1 | 0 | 1;
  geometry: VoxelAgentGeometryKind;
  key: string;
  position: VoxelVector3;
  rotation: VoxelVector3;
  size: VoxelVector3;
};

export type VoxelAgentGeometryKind = "box" | "head" | "limb" | "torso";

export const VOXEL_AGENT_GEOMETRY_KINDS: readonly VoxelAgentGeometryKind[] = [
  "box",
  "head",
  "limb",
  "torso",
];

export function buildVoxelAgentInstanceParts(
  agents: VoxelAgentPlan[],
): VoxelAgentInstancePart[] {
  return agents.flatMap((agent) => {
    const { appearance } = agent;
    const heightScale = appearance.heightScale;
    const status = agent.source.status;
    const restingOffset = status === "resting" ? -0.1 * heightScale : 0;
    const part = (
      key: string,
      position: [number, number, number],
      size: [number, number, number],
      color: number,
      options: {
        gaitDirection?: VoxelAgentInstancePart["gaitDirection"];
        geometry?: VoxelAgentGeometryKind;
        rotation?: [number, number, number];
      } = {},
    ): VoxelAgentInstancePart => ({
      agentId: agent.id,
      color,
      gaitDirection: options.gaitDirection ?? 0,
      geometry: options.geometry ?? "box",
      key: `${agent.id}:${key}`,
      position: { x: position[0], y: position[1], z: position[2] },
      rotation: {
        x: options.rotation?.[0] ?? 0,
        y: options.rotation?.[1] ?? 0,
        z: options.rotation?.[2] ?? 0,
      },
      size: { x: size[0], y: size[1], z: size[2] },
    });
    const leftArmPose = resolveArmPose(status, "left");
    const rightArmPose = resolveArmPose(status, "right");
    const leftLegPose = resolveLegPose(status, "left");
    const rightLegPose = resolveLegPose(status, "right");
    const parts = [
      part(
        "torso",
        [0, 0.47 * heightScale + restingOffset, 0],
        [0.27, 0.4 * heightScale, 0.21],
        appearance.torso,
        { geometry: "torso" },
      ),
      part(
        "head",
        [0, 0.76 * heightScale + restingOffset, 0],
        [0.2, 0.21, 0.19],
        appearance.skin,
        { geometry: "head" },
      ),
      part(
        "hair",
        [0, 0.835 * heightScale + restingOffset, -0.018],
        [0.205, 0.105, 0.195],
        appearance.hair,
        { geometry: "head" },
      ),
      part(
        "status",
        [0.075, 0.525 * heightScale + restingOffset, 0.112],
        [0.055, 0.055, 0.025],
        VOXEL_MATERIAL_COLORS[getAgentMaterial(agent.source.status)],
      ),
      part(
        "sleeve-left",
        [-0.165, 0.515 * heightScale + restingOffset + leftArmPose.y, leftArmPose.z],
        [0.075, 0.2, 0.075],
        appearance.torso,
        {
          gaitDirection: leftArmPose.gaitDirection,
          geometry: "limb",
          rotation: leftArmPose.rotation,
        },
      ),
      part(
        "sleeve-right",
        [0.165, 0.515 * heightScale + restingOffset + rightArmPose.y, rightArmPose.z],
        [0.075, 0.2, 0.075],
        appearance.torso,
        {
          gaitDirection: rightArmPose.gaitDirection,
          geometry: "limb",
          rotation: rightArmPose.rotation,
        },
      ),
      part(
        "forearm-left",
        [-0.165, 0.335 * heightScale + restingOffset + leftArmPose.y, leftArmPose.z],
        [0.062, 0.18, 0.062],
        appearance.skin,
        {
          gaitDirection: leftArmPose.gaitDirection,
          geometry: "limb",
          rotation: leftArmPose.rotation,
        },
      ),
      part(
        "forearm-right",
        [0.165, 0.335 * heightScale + restingOffset + rightArmPose.y, rightArmPose.z],
        [0.062, 0.18, 0.062],
        appearance.skin,
        {
          gaitDirection: rightArmPose.gaitDirection,
          geometry: "limb",
          rotation: rightArmPose.rotation,
        },
      ),
      part(
        "leg-left",
        [-0.075, leftLegPose.y, leftLegPose.z],
        [0.075, 0.26 * heightScale, 0.075],
        appearance.trousers,
        { gaitDirection: 1, geometry: "limb", rotation: leftLegPose.rotation },
      ),
      part(
        "leg-right",
        [0.075, rightLegPose.y, rightLegPose.z],
        [0.075, 0.26 * heightScale, 0.075],
        appearance.trousers,
        { gaitDirection: -1, geometry: "limb", rotation: rightLegPose.rotation },
      ),
      part(
        "shoe-left",
        [-0.075, leftLegPose.y - 0.14 * heightScale, leftLegPose.z + 0.025],
        [0.095, 0.055, 0.14],
        appearance.hair,
        { gaitDirection: 1, rotation: leftLegPose.rotation },
      ),
      part(
        "shoe-right",
        [0.075, rightLegPose.y - 0.14 * heightScale, rightLegPose.z + 0.025],
        [0.095, 0.055, 0.14],
        appearance.hair,
        { gaitDirection: -1, rotation: rightLegPose.rotation },
      ),
    ];
    if (status === "working") {
      parts.push(
        part(
          "work-prop",
          [0, 0.34 * heightScale, 0.24],
          [0.28, 0.035, 0.2],
          appearance.accent,
          { rotation: [0.12, 0, 0] },
        ),
      );
    }
    if (status === "resting") {
      parts.push(
        part(
          "book",
          [0, 0.24 * heightScale, 0.2],
          [0.22, 0.035, 0.16],
          appearance.accent,
          { rotation: [0.32, 0, 0] },
        ),
      );
    }
    if (appearance.accessory === "backpack") {
      parts.push(
        part(
          "backpack",
          [0, 0.4 * heightScale + restingOffset, -0.12],
          [0.19, 0.3, 0.08],
          appearance.accent,
        ),
      );
    }
    if (appearance.accessory === "satchel") {
      parts.push(
        part(
          "satchel",
          [0.15, 0.31 * heightScale + restingOffset, -0.02],
          [0.09, 0.16, 0.08],
          appearance.accent,
        ),
      );
    }
    return parts;
  });
}

function resolveArmPose(
  status: VoxelAgentPlan["source"]["status"],
  side: "left" | "right",
): { gaitDirection: -1 | 0 | 1; rotation: [number, number, number]; y: number; z: number } {
  const sign = side === "left" ? -1 : 1;
  if (status === "moving") {
    return { gaitDirection: side === "left" ? -1 : 1, rotation: [0, 0, 0], y: 0, z: 0 };
  }
  if (status === "talking") {
    return { gaitDirection: 0, rotation: [-0.18, 0, sign * 0.82], y: 0.06, z: 0.03 };
  }
  if (status === "working") {
    return { gaitDirection: 0, rotation: [-1.05, 0, sign * 0.12], y: -0.02, z: 0.1 };
  }
  if (status === "resting") {
    return { gaitDirection: 0, rotation: [-0.92, 0, sign * 0.08], y: -0.02, z: 0.09 };
  }
  return { gaitDirection: 0, rotation: [0, 0, 0], y: 0, z: 0 };
}

function resolveLegPose(
  status: VoxelAgentPlan["source"]["status"],
  side: "left" | "right",
): { rotation: [number, number, number]; y: number; z: number } {
  if (status === "resting") {
    return {
      rotation: [-1.12, 0, side === "left" ? -0.08 : 0.08],
      y: 0.16,
      z: 0.11,
    };
  }
  return { rotation: [0, 0, 0], y: 0.15, z: 0 };
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
