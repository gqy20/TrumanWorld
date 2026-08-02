import type { TimeOfDay } from "@/lib/world-utils";

export const WORLD_V2_PALETTE = {
  moss: "#667C5B",
  leaf: "#7F9A68",
  brick: "#A45345",
  ember: "#D86F45",
  limewash: "#E7E7E1",
  slate: "#526B7A",
  ink: "#172033",
  paving: "#B9B4AA",
  windowAmber: "#F2B45B",
  night: "#172338",
} as const;

export type WorldLightingProfile = {
  background: string;
  fog: string;
  hemisphereSky: string;
  hemisphereGround: string;
  hemisphereIntensity: number;
  sun: string;
  sunIntensity: number;
  sunPosition: [number, number, number];
  exposure: number;
  windowEmissiveIntensity: number;
};

const PROFILES: Record<TimeOfDay, WorldLightingProfile> = {
  dawn: {
    background: "#B8C8C4", fog: "#C7D1CC", hemisphereSky: "#C8D9D7",
    hemisphereGround: "#667C5B", hemisphereIntensity: 1.45,
    sun: "#F2B45B", sunIntensity: 2.2, sunPosition: [-7, 7, 4], exposure: 1.04,
    windowEmissiveIntensity: 0.55,
  },
  morning: {
    background: "#CCD9D2", fog: "#D7DED6", hemisphereSky: "#E4ECE8",
    hemisphereGround: "#667C5B", hemisphereIntensity: 1.6,
    sun: "#FFF0CE", sunIntensity: 2.65, sunPosition: [-5, 10, 6], exposure: 1.08,
    windowEmissiveIntensity: 0.16,
  },
  noon: {
    background: "#D7E1DB", fog: "#E1E6DF", hemisphereSky: "#F1F4EF",
    hemisphereGround: "#72846A", hemisphereIntensity: 1.7,
    sun: "#FFF7E6", sunIntensity: 2.8, sunPosition: [4, 12, 3], exposure: 1.05,
    windowEmissiveIntensity: 0.04,
  },
  afternoon: {
    background: "#D4D9CF", fog: "#DDDCD1", hemisphereSky: "#ECE8DD",
    hemisphereGround: "#756F58", hemisphereIntensity: 1.55,
    sun: "#FFD49A", sunIntensity: 2.55, sunPosition: [7, 8, -4], exposure: 1.04,
    windowEmissiveIntensity: 0.1,
  },
  evening: {
    background: "#8B9191", fog: "#969A95", hemisphereSky: "#A3A5A4",
    hemisphereGround: "#4D584D", hemisphereIntensity: 1.2,
    sun: "#F19A69", sunIntensity: 2.1, sunPosition: [8, 5, -5], exposure: 0.94,
    windowEmissiveIntensity: 0.75,
  },
  night: {
    background: WORLD_V2_PALETTE.night, fog: "#26353D", hemisphereSky: "#526B7A",
    hemisphereGround: "#172033", hemisphereIntensity: 0.72,
    sun: "#B9CEE6", sunIntensity: 1.15, sunPosition: [-5, 9, -3], exposure: 0.74,
    windowEmissiveIntensity: 1.2,
  },
};

export function resolveWorldLightingProfile(timeOfDay?: TimeOfDay): WorldLightingProfile {
  return PROFILES[timeOfDay ?? "noon"];
}
