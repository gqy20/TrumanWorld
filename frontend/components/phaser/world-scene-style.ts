import type { SceneAgent, SceneStagePalette } from "@/lib/world-scene-adapter";

export const CANVAS_WIDTH = 800;
export const CANVAS_HEIGHT = 600;
export const LOCATION_WIDTH = 88;
export const LOCATION_HEIGHT = 108;
export const SCENE_PADDING_X = 120;
export const SCENE_PADDING_Y = 90;
export const PIXEL_SCALE = 1.85;
export const BUILDING_TEXTURE_SIZE = 24;
export const AGENT_TEXTURE_SIZE = 16;
export const GROUND_TEXTURE_SIZE = 32;
export const ISO_TILE_WIDTH = 96;
export const ISO_TILE_HEIGHT = 48;
export const ISO_GRID_COLUMNS = 8;
export const ISO_GRID_ROWS = 8;
export const ISO_ORIGIN_X = CANVAS_WIDTH / 2;
export const ISO_ORIGIN_Y = 78;

export type StagePalette = {
  backgroundColor: string;
  headerColor: number;
  headerAlpha: number;
  vignetteColor: number;
  vignetteAlpha: number;
  labelColor: string;
};

export function parseRgbaColor(input: string): number {
  const match = input.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/i);
  if (!match) {
    return 0xffffff;
  }
  const [, r, g, b] = match;
  return (Number(r) << 16) + (Number(g) << 8) + Number(b);
}

export function getLocationColor(locationType: string): number {
  switch (locationType) {
    case "cafe":
      return 0xf59e0b;
    case "plaza":
      return 0x0ea5e9;
    case "park":
      return 0x10b981;
    case "office":
      return 0x2563eb;
    case "home":
      return 0xec4899;
    default:
      return 0x64748b;
  }
}

export function getAgentColor(status: SceneAgent["status"]): number {
  switch (status) {
    case "moving":
      return 0x38bdf8;
    case "talking":
      return 0xf97316;
    case "working":
      return 0x22c55e;
    case "resting":
      return 0xa78bfa;
    default:
      return 0xf8fafc;
  }
}

export function getLocationGlyph(locationType: string): string {
  switch (locationType) {
    case "cafe":
      return "C";
    case "plaza":
      return "P";
    case "park":
      return "G";
    case "office":
      return "O";
    case "home":
      return "H";
    default:
      return "L";
  }
}

export function getConfiguredLocationTextureKey(
  visualPreset: string,
  locationType: string,
): string {
  return `pixel-building-${visualPreset}-${locationType}`;
}

export function getAgentMarker(status: SceneAgent["status"]): string {
  switch (status) {
    case "moving":
      return ">";
    case "talking":
      return "~";
    case "working":
      return "+";
    case "resting":
      return "z";
    default:
      return ".";
  }
}

export function getAgentTextureKey(status: SceneAgent["status"]): string {
  return `pixel-agent-${status}`;
}

export function getConfiguredAgentTextureKey(
  visualPreset: string,
  status: SceneAgent["status"],
): string {
  return `pixel-agent-${visualPreset}-${status}`;
}

export function getArrowAngleDegrees(fromX: number, fromY: number, toX: number, toY: number) {
  return Math.atan2(toY - fromY, toX - fromX) * (180 / Math.PI) + 90;
}

export function getStagePalette(theme?: string): StagePalette {
  switch (theme) {
    case "campus_night":
      return {
        backgroundColor: "#e8f3df",
        headerColor: 0xd7ead0,
        headerAlpha: 0,
        vignetteColor: 0x3f5f3a,
        vignetteAlpha: 0.08,
        labelColor: "#dcfce7",
      };
    case "seaside_night":
      return {
        backgroundColor: "#e6f1f4",
        headerColor: 0xcde5ea,
        headerAlpha: 0,
        vignetteColor: 0x355866,
        vignetteAlpha: 0.08,
        labelColor: "#e2e8f0",
      };
    default:
      return {
        backgroundColor: "#eef5e8",
        headerColor: 0xdcebd5,
        headerAlpha: 0,
        vignetteColor: 0x36543a,
        vignetteAlpha: 0.08,
        labelColor: "#e2e8f0",
      };
  }
}

export function mergeStagePalette(
  fallback: StagePalette,
  override?: SceneStagePalette,
): StagePalette {
  return {
    backgroundColor: override?.backgroundColor ?? fallback.backgroundColor,
    headerColor: override?.headerColor ? parseRgbaColor(override.headerColor) : fallback.headerColor,
    headerAlpha: override?.headerAlpha ?? fallback.headerAlpha,
    vignetteColor: override?.vignetteColor
      ? parseRgbaColor(override.vignetteColor)
      : fallback.vignetteColor,
    vignetteAlpha: override?.vignetteAlpha ?? fallback.vignetteAlpha,
    labelColor: override?.labelColor ?? fallback.labelColor,
  };
}
