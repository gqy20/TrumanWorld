import { EVENT_MOVE } from "@/lib/simulation-protocol";
import type { AgentSummary, WorldSnapshot } from "@/lib/types";
import { calculateLocationHeat, type LocationHeatConfig } from "@/lib/world-utils";

export interface LocationNode {
  id: string;
  name: string;
  type: string;
  x: number;
  y: number;
  capacity: number;
  occupantCount: number;
  occupants: AgentSummary[];
  heat: number;
}

export interface PositionedLocationNode extends LocationNode {
  svgX: number;
  svgY: number;
}

export interface LocationLink {
  source: string;
  target: string;
}

export interface MovePath {
  id: string;
  fromX: number;
  fromY: number;
  toX: number;
  toY: number;
}

export type ViewBox = {
  x: number;
  y: number;
  width: number;
  height: number;
};

export type LocationStyle = {
  icon: string;
  color: string;
  bgColor: string;
  label: string;
};

export const AGENT_COLORS = [
  "#fbbf24",
  "#60a5fa",
  "#a78bfa",
  "#f472b6",
  "#34d399",
  "#fb923c",
];
export const SVG_W = 700;
export const SVG_H = 440;
export const PADDING = 88;
export const VIEWBOX_MIN_WIDTH = 300;
export const VIEWBOX_MAX_WIDTH = SVG_W * 2;
export const NODE_SCALE = 0.7;

export const LOCATION_STYLES: Record<string, LocationStyle> = {
  cafe: { icon: "☕", color: "#d97706", bgColor: "#fef3c7", label: "咖啡馆" },
  plaza: { icon: "🌳", color: "#0284c7", bgColor: "#e0f2fe", label: "广场" },
  park: { icon: "🌲", color: "#059669", bgColor: "#d1fae5", label: "公园" },
  shop: { icon: "🏪", color: "#7c3aed", bgColor: "#ede9fe", label: "商场" },
  home: { icon: "🏠", color: "#db2777", bgColor: "#fce7f3", label: "住宅" },
  office: { icon: "🏢", color: "#0369a1", bgColor: "#e0f2fe", label: "办公室" },
  hospital: { icon: "🏥", color: "#dc2626", bgColor: "#fee2e2", label: "医院" },
  default: { icon: "📍", color: "#64748b", bgColor: "#f8fafc", label: "地点" },
};

export function agentColor(agentId: string): string {
  let hash = 0;
  for (let index = 0; index < agentId.length; index++) {
    hash = agentId.charCodeAt(index) + ((hash << 5) - hash);
  }
  return AGENT_COLORS[Math.abs(hash) % AGENT_COLORS.length];
}

export function scaleCoordinate(value: number, min: number, max: number, size: number): number {
  if (min === max) {
    return size / 2;
  }

  return PADDING + ((value - min) / (max - min)) * (size - PADDING * 2);
}

export function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

export function clampViewBox(next: ViewBox): ViewBox {
  const width = clamp(next.width, VIEWBOX_MIN_WIDTH, VIEWBOX_MAX_WIDTH);
  const height = (width / SVG_W) * SVG_H;
  const x = clamp(next.x, -(width - SVG_W) / 2, SVG_W - width / 2);
  const y = clamp(next.y, -(height - SVG_H) / 2, SVG_H - height / 2);

  return { x, y, width, height };
}

export function buildMapData(world: WorldSnapshot) {
  const hmc = world.health_metrics_config;
  const heatConfig: LocationHeatConfig | undefined = hmc
    ? {
        normalizationBaseline: hmc.heat_normalization_baseline,
        thresholdVeryActive: hmc.heat_threshold_very_active,
        thresholdActive: hmc.heat_threshold_active,
        thresholdMild: hmc.heat_threshold_mild,
        glowThreshold: hmc.heat_glow_threshold,
      }
    : undefined;

  const rawNodes: LocationNode[] = world.locations.map((location) => ({
    id: location.id,
    name: location.name,
    type: location.location_type,
    x: location.x,
    y: location.y,
    capacity: location.capacity,
    occupantCount: location.occupants.length,
    occupants: location.occupants,
    heat: calculateLocationHeat(location.id, world.recent_events, heatConfig),
  }));

  const xValues = rawNodes.map((node) => node.x);
  const yValues = rawNodes.map((node) => node.y);
  const minX = xValues.length > 0 ? Math.min(...xValues) : 0;
  const maxX = xValues.length > 0 ? Math.max(...xValues) : 1;
  const minY = yValues.length > 0 ? Math.min(...yValues) : 0;
  const maxY = yValues.length > 0 ? Math.max(...yValues) : 1;

  const nodes: PositionedLocationNode[] = rawNodes.map((node) => ({
    ...node,
    svgX: scaleCoordinate(node.x, minX, maxX, SVG_W),
    svgY: scaleCoordinate(node.y, minY, maxY, SVG_H),
  }));

  const links = buildLocationLinks(nodes);
  const movePaths = buildMovePaths(world, nodes);
  const homeNode = nodes.find((node) => node.type === "home");
  const plazaNode = nodes.find((node) => node.type === "plaza");
  const officeNode = nodes.find((node) => node.type === "office");

  let mainRoadPath = "";
  if (homeNode && plazaNode && officeNode) {
    mainRoadPath = `M ${homeNode.svgX} ${homeNode.svgY} Q ${plazaNode.svgX} ${plazaNode.svgY} ${officeNode.svgX} ${officeNode.svgY}`;
  }

  const maxSvgY = nodes.length > 0 ? Math.max(...nodes.map((node) => node.svgY)) : SVG_H / 2;
  const coastY = Math.min(maxSvgY + 65, SVG_H - 15);
  const coastPath = `M -20 ${coastY + 25} C 160 ${coastY - 10} 360 ${coastY + 40} 560 ${coastY - 5} S 720 ${coastY + 15} 740 ${coastY}`;

  return { nodes, links, movePaths, mainRoadPath, coastPath, heatConfig };
}

function buildLocationLinks(nodes: PositionedLocationNode[]): LocationLink[] {
  const links: LocationLink[] = [];
  const maxNeighbors = Math.min(2, Math.max(0, nodes.length - 1));

  for (let index = 0; index < nodes.length; index++) {
    const source = nodes[index];
    const nearest = nodes
      .filter((_, otherIndex) => otherIndex !== index)
      .map((target) => ({
        id: target.id,
        distance: Math.hypot(source.svgX - target.svgX, source.svgY - target.svgY),
      }))
      .sort((left, right) => left.distance - right.distance)
      .slice(0, maxNeighbors);

    for (const candidate of nearest) {
      const exists = links.some(
        (link) =>
          (link.source === source.id && link.target === candidate.id) ||
          (link.source === candidate.id && link.target === source.id),
      );
      if (!exists) {
        links.push({ source: source.id, target: candidate.id });
      }
    }
  }

  return links;
}

function buildMovePaths(world: WorldSnapshot, nodes: PositionedLocationNode[]): MovePath[] {
  return world.recent_events
    .filter((event) => event.event_type === EVENT_MOVE && event.location_id)
    .map((event) => {
      const toLocationId =
        typeof event.payload.to_location_id === "string" ? event.payload.to_location_id : undefined;
      if (!toLocationId || !event.location_id) {
        return null;
      }

      const fromLocation = nodes.find((node) => node.id === event.location_id);
      const toLocation = nodes.find((node) => node.id === toLocationId);
      if (!fromLocation || !toLocation) {
        return null;
      }

      return {
        id: event.id,
        fromX: fromLocation.svgX,
        fromY: fromLocation.svgY,
        toX: toLocation.svgX,
        toY: toLocation.svgY,
      };
    })
    .filter((path): path is MovePath => path !== null)
    .slice(0, 4);
}
