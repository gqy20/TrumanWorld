/**
 * 像素风地图主题规则
 * - PIXEL: 基础像素单位，所有坐标尽量取整为 PIXEL 的倍数
 * - 每种建筑类型：4 色调色板（屋顶、左立面、右立面、高光/窗户）+ 描边色
 * - 昼夜两套背景色板
 * - 路砖颜色
 */

/** 基础像素单位 */
export const PIXEL = 4;

/** 对齐到最近的像素网格 */
export function px(value: number): number {
  return Math.round(value / PIXEL) * PIXEL;
}

export type PixelBuildingPalette = {
  /** 图标 emoji */
  icon: string;
  /** 地点类型标签 */
  label: string;
  /** 屋顶色 */
  roof: string;
  /** 左立面色（亮面） */
  left: string;
  /** 右立面色（暗面） */
  right: string;
  /** 窗户 / 高光色 */
  window: string;
  /** 统一深描边 */
  outline: string;
  /** 活跃状态：屋顶灯颜色 */
  activeLamp: string;
};

export const PIXEL_BUILDING_PALETTES: Record<string, PixelBuildingPalette> = {
  cafe: {
    icon: "☕",
    label: "咖啡馆",
    roof: "#f59e0b",
    left: "#fbbf24",
    right: "#d97706",
    window: "#fef3c7",
    outline: "#78350f",
    activeLamp: "#fcd34d",
  },
  plaza: {
    icon: "⛲",
    label: "广场",
    roof: "#38bdf8",
    left: "#7dd3fc",
    right: "#0284c7",
    window: "#e0f2fe",
    outline: "#075985",
    activeLamp: "#bae6fd",
  },
  park: {
    icon: "🌲",
    label: "公园",
    roof: "#22c55e",
    left: "#4ade80",
    right: "#15803d",
    window: "#dcfce7",
    outline: "#14532d",
    activeLamp: "#86efac",
  },
  shop: {
    icon: "🏪",
    label: "商店",
    roof: "#8b5cf6",
    left: "#a78bfa",
    right: "#6d28d9",
    window: "#ede9fe",
    outline: "#3b0764",
    activeLamp: "#c4b5fd",
  },
  home: {
    icon: "🏠",
    label: "住宅",
    roof: "#ec4899",
    left: "#f472b6",
    right: "#be185d",
    window: "#fce7f3",
    outline: "#831843",
    activeLamp: "#fbcfe8",
  },
  office: {
    icon: "🏢",
    label: "办公室",
    roof: "#3b82f6",
    left: "#60a5fa",
    right: "#1d4ed8",
    window: "#dbeafe",
    outline: "#1e3a8a",
    activeLamp: "#93c5fd",
  },
  hospital: {
    icon: "🏥",
    label: "医院",
    roof: "#ef4444",
    left: "#f87171",
    right: "#b91c1c",
    window: "#fee2e2",
    outline: "#7f1d1d",
    activeLamp: "#fca5a5",
  },
  default: {
    icon: "📍",
    label: "地点",
    roof: "#64748b",
    left: "#94a3b8",
    right: "#475569",
    window: "#f1f5f9",
    outline: "#1e293b",
    activeLamp: "#cbd5e1",
  },
};

export function getPixelPalette(locationType: string): PixelBuildingPalette {
  return PIXEL_BUILDING_PALETTES[locationType] ?? PIXEL_BUILDING_PALETTES.default;
}

/** 昼夜路砖颜色 */
export const ROAD_COLORS = {
  day: {
    tile: "#c4bfb0",
    tileAlt: "#b8b2a2",
    outline: "#a09880",
  },
  night: {
    tile: "#2c3347",
    tileAlt: "#252d3e",
    outline: "#1a2035",
  },
};

/** 海岸像素带颜色 */
export const COAST_COLORS = {
  day: "#93c5fd",
  night: "#1e3a5f",
};

/** 热力边框颜色：按 heat 值映射 */
export function getHeatOutlineColor(heat: number): string {
  if (heat > 0.7) return "#ef4444";
  if (heat > 0.4) return "#f59e0b";
  if (heat > 0.1) return "#22c55e";
  return "transparent";
}
