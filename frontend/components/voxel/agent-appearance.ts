export type VoxelAgentAppearance = {
  torso: number;
  hair: number;
  skin: number;
  trousers: number;
  accent: number;
  heightScale: number;
  accessory: "backpack" | "satchel" | "none";
};

const PALETTES = [
  { torso: 0xc95f4b, hair: 0x302923, skin: 0xf2bd91, trousers: 0x27364a, accent: 0xf2c14e },
  { torso: 0x3f7f78, hair: 0x24262b, skin: 0xd99b72, trousers: 0x293341, accent: 0xe68a55 },
  { torso: 0x6674a8, hair: 0x4a3025, skin: 0xf0c7a4, trousers: 0x313747, accent: 0x8fcf72 },
  { torso: 0x9a6684, hair: 0x292329, skin: 0xb97855, trousers: 0x263849, accent: 0x74c6d8 },
] as const;

export function resolveAgentAppearance(agentId: string): VoxelAgentAppearance {
  const hash = stableHash(agentId);
  const palette = PALETTES[hash % PALETTES.length];
  const accessories: VoxelAgentAppearance["accessory"][] = ["backpack", "satchel", "none"];
  return {
    ...palette,
    heightScale: [0.94, 1, 1.06][Math.floor(hash / PALETTES.length) % 3],
    accessory: accessories[Math.floor(hash / 7) % accessories.length],
  };
}

function stableHash(value: string): number {
  let hash = 2166136261;
  for (const character of value) {
    hash ^= character.charCodeAt(0);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}
