import type { VoxelAgentPlan } from "../types";
import { buildVoxelAgentInstanceParts } from "../agent-instances";

function makeAgent(accessory: VoxelAgentPlan["appearance"]["accessory"]): VoxelAgentPlan {
  return {
    id: `agent-${accessory}`,
    source: {
      id: `agent-${accessory}`,
      name: "Mei",
      locationId: "cafe",
      status: "moving",
      slotIndex: 0,
    },
    anchor: {
      position: { x: 2, y: 0.04, z: 3 },
      size: { x: 0.46, y: 0.04, z: 0.46 },
    },
    appearance: {
      torso: 0x111111,
      hair: 0x222222,
      skin: 0x333333,
      trousers: 0x444444,
      accent: 0x555555,
      heightScale: 1,
      accessory,
    },
  };
}

describe("voxel agent instances", () => {
  it("packs a plain agent into eight colored box instances", () => {
    const parts = buildVoxelAgentInstanceParts([makeAgent("none")]);

    expect(parts).toHaveLength(8);
    expect(new Set(parts.map((part) => part.key)).size).toBe(parts.length);
    expect(parts.every((part) => part.agentId === "agent-none")).toBe(true);
  });

  it("adds one optional accessory instance", () => {
    expect(buildVoxelAgentInstanceParts([makeAgent("backpack")])).toHaveLength(9);
    expect(buildVoxelAgentInstanceParts([makeAgent("satchel")])).toHaveLength(9);
  });

  it("marks opposing legs for gait transforms", () => {
    const legs = buildVoxelAgentInstanceParts([makeAgent("none")]).filter(
      (part) => part.gaitDirection !== 0,
    );

    expect(legs.map((part) => part.gaitDirection)).toEqual([1, -1]);
  });
});
