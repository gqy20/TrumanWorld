import type { VoxelAgentPlan } from "../types";
import { buildVoxelAgentInstanceParts } from "../agent-instances";

function makeAgent(
  accessory: VoxelAgentPlan["appearance"]["accessory"],
  status: VoxelAgentPlan["source"]["status"] = "moving",
): VoxelAgentPlan {
  return {
    id: `agent-${accessory}`,
    source: {
      id: `agent-${accessory}`,
      name: "Mei",
      locationId: "cafe",
      status,
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
  it("packs a plain agent into a shared low-poly geometry kit", () => {
    const parts = buildVoxelAgentInstanceParts([makeAgent("none")]);

    expect(parts).toHaveLength(12);
    expect(new Set(parts.map((part) => part.key)).size).toBe(parts.length);
    expect(parts.every((part) => part.agentId === "agent-none")).toBe(true);
    expect(new Set(parts.map((part) => part.geometry))).toEqual(
      new Set(["box", "head", "limb", "torso"]),
    );
  });

  it("adds one optional accessory instance", () => {
    expect(buildVoxelAgentInstanceParts([makeAgent("backpack")])).toHaveLength(13);
    expect(buildVoxelAgentInstanceParts([makeAgent("satchel")])).toHaveLength(13);
  });

  it("marks opposing legs for gait transforms", () => {
    const parts = buildVoxelAgentInstanceParts([makeAgent("none")]);
    const legs = parts.filter((part) => part.key.includes(":leg-"));
    const sleeves = parts.filter((part) => part.key.includes(":sleeve-"));
    const forearms = parts.filter((part) => part.key.includes(":forearm-"));

    expect(legs.map((part) => part.gaitDirection)).toEqual([1, -1]);
    expect(sleeves.map((part) => part.gaitDirection)).toEqual([-1, 1]);
    expect(forearms.map((part) => part.gaitDirection)).toEqual([-1, 1]);
  });

  it("gives conversation, work and rest distinct silhouettes", () => {
    const talking = buildVoxelAgentInstanceParts([makeAgent("none", "talking")]);
    const working = buildVoxelAgentInstanceParts([makeAgent("none", "working")]);
    const resting = buildVoxelAgentInstanceParts([makeAgent("none", "resting")]);

    expect(talking.find((part) => part.key.endsWith(":sleeve-left"))?.rotation.z).not.toBe(0);
    expect(working.some((part) => part.key.endsWith(":work-prop"))).toBe(true);
    expect(resting.some((part) => part.key.endsWith(":book"))).toBe(true);
    expect(resting.find((part) => part.key.endsWith(":leg-left"))?.rotation.x).toBeLessThan(0);
  });

  it("uses clothing for sleeves and skin for forearms", () => {
    const parts = buildVoxelAgentInstanceParts([makeAgent("none")]);

    expect(parts.find((part) => part.key.endsWith(":sleeve-left"))?.color).toBe(0x111111);
    expect(parts.find((part) => part.key.endsWith(":forearm-left"))?.color).toBe(0x333333);
    expect(parts.find((part) => part.key.endsWith(":shoe-left"))?.color).toBe(0x222222);
  });
});
