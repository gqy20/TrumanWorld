import type { SceneAgent, SceneStagePalette } from "@/lib/world-scene-adapter";

export const CANVAS_WIDTH = 800;
export const CANVAS_HEIGHT = 600;
export const LOCATION_WIDTH = 86;
export const LOCATION_HEIGHT = 104;
export const SCENE_PADDING_X = 120;
export const SCENE_PADDING_Y = 90;
export const PIXEL_SCALE = 3;
export const BUILDING_TEXTURE_SIZE = 24;
export const AGENT_TEXTURE_SIZE = 16;
export const GROUND_TEXTURE_SIZE = 32;
export const ISO_TILE_WIDTH = 76;
export const ISO_TILE_HEIGHT = 38;
export const ISO_GRID_COLUMNS = 7;
export const ISO_GRID_ROWS = 7;
export const ISO_ORIGIN_X = CANVAS_WIDTH / 2;
export const ISO_ORIGIN_Y = 132;

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
        backgroundColor: "#112317",
        headerColor: 0x1d4d2b,
        headerAlpha: 0.34,
        vignetteColor: 0x08140d,
        vignetteAlpha: 0.18,
        labelColor: "#dcfce7",
      };
    case "seaside_night":
      return {
        backgroundColor: "#0f172a",
        headerColor: 0x172554,
        headerAlpha: 0.42,
        vignetteColor: 0x0f172a,
        vignetteAlpha: 0.16,
        labelColor: "#e2e8f0",
      };
    default:
      return {
        backgroundColor: "#101826",
        headerColor: 0x1f2937,
        headerAlpha: 0.38,
        vignetteColor: 0x020617,
        vignetteAlpha: 0.18,
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
