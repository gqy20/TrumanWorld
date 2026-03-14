"use client";

import { useEffect, useMemo, useRef, useState, type KeyboardEvent, type PointerEvent, type WheelEvent } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { WorldMapAgent } from "@/components/world-map-agent";
import { WorldMapBuilding, getLocationBuildingStyle } from "@/components/world-map-building";
import { EVENT_MOVE } from "@/lib/simulation-protocol";
import type { AgentSummary, WorldSnapshot } from "@/lib/types";
import { getBuildingFootprint, getFrontArcPosition, sortByRenderOrder, type BuildingFootprint } from "@/lib/world-map-layout";
import { COAST_COLORS, ROAD_COLORS } from "@/lib/world-map-pixel-theme";
import { calculateLocationHeat, getHeatLevel, getTimeOfDay, getTimeOfDayStyle, type LocationHeatConfig } from "@/lib/world-utils";

interface LocationNode {
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

interface PositionedLocationNode extends LocationNode {
  svgX: number;
  svgY: number;
  footprint: BuildingFootprint;
}

interface LocationLink {
  source: string;
  target: string;
}

interface MovePath {
  id: string;
  fromX: number;
  fromY: number;
  toX: number;
  toY: number;
}

interface TownMapProps {
  world: WorldSnapshot;
  agentNameMap: Record<string, string>;
  onLocationClick?: (locationId: string) => void;
  onAgentClick?: (agentId: string) => void;
  highlightedLocationId?: string | null;
}

const AGENT_COLORS = ["#fbbf24", "#60a5fa", "#a78bfa", "#f472b6", "#34d399", "#fb923c"];
const SVG_W = 700;
const SVG_H = 440;
const PADDING = 88;
const VIEWBOX_MIN_WIDTH = 300;
// 缩小时 viewBox 可超出 SVG 画布，设为 SVG_W 的 2 倍即可缩小到原始大小的 50%
const VIEWBOX_MAX_WIDTH = SVG_W * 2;
// 节点整体缩放系数，1.0 = 原始大小
const NODE_SCALE = 0.7;

type ViewBox = {
  x: number;
  y: number;
  width: number;
  height: number;
};

function agentColor(agentId: string): string {
  let hash = 0;
  for (let index = 0; index < agentId.length; index++) {
    hash = agentId.charCodeAt(index) + ((hash << 5) - hash);
  }
  return AGENT_COLORS[Math.abs(hash) % AGENT_COLORS.length];
}

function scaleCoordinate(value: number, min: number, max: number, size: number) {
  if (min === max) {
    return size / 2;
  }

  return PADDING + ((value - min) / (max - min)) * (size - PADDING * 2);
}

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

function clampViewBox(next: ViewBox): ViewBox {
  const width = clamp(next.width, VIEWBOX_MIN_WIDTH, VIEWBOX_MAX_WIDTH);
  const height = (width / SVG_W) * SVG_H;
  const x = clamp(next.x, -(width - SVG_W) / 2, SVG_W - width / 2);
  const y = clamp(next.y, -(height - SVG_H) / 2, SVG_H - height / 2);

  return { x, y, width, height };
}

function buildMapData(world: WorldSnapshot) {
  const hmc = world.health_metrics_config;
  const heatConfig: LocationHeatConfig | undefined = hmc ? {
    normalizationBaseline: hmc.heat_normalization_baseline,
    thresholdVeryActive: hmc.heat_threshold_very_active,
    thresholdActive: hmc.heat_threshold_active,
    thresholdMild: hmc.heat_threshold_mild,
    glowThreshold: hmc.heat_glow_threshold,
  } : undefined;

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

  const nodes: PositionedLocationNode[] = rawNodes.map((node) => {
    return {
      ...node,
      svgX: scaleCoordinate(node.x, minX, maxX, SVG_W),
      svgY: scaleCoordinate(node.y, minY, maxY, SVG_H),
      footprint: getBuildingFootprint(node.type, node.capacity, node.heat),
    };
  });
  const sortedNodes = sortByRenderOrder(nodes);

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

  const movePaths: MovePath[] = world.recent_events
    .filter((event) => event.event_type === EVENT_MOVE && event.location_id)
    .map((event) => {
      const toLocationId =
        typeof event.payload.to_location_id === "string" ? event.payload.to_location_id : undefined;
      if (!toLocationId || !event.location_id) {
        return null;
      }

      const fromLocation = sortedNodes.find((node) => node.id === event.location_id);
      const toLocation = sortedNodes.find((node) => node.id === toLocationId);
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

  // 动态装饰路径
  const homeNode = sortedNodes.find((n) => n.type === "home");
  const plazaNode = sortedNodes.find((n) => n.type === "plaza");
  const officeNode = sortedNodes.find((n) => n.type === "office");

  // 主街道：经过住宅 -> 广场 -> 办公室，用二次贝塞尔穿过三点
  let mainRoadPath = "";
  if (homeNode && plazaNode && officeNode) {
    // 以广场为控制点，让曲线自然弯曲穿过三个节点区域
    const cpX = plazaNode.svgX;
    const cpY = plazaNode.svgY;
    mainRoadPath = `M ${homeNode.svgX} ${homeNode.svgY} Q ${cpX} ${cpY} ${officeNode.svgX} ${officeNode.svgY}`;
  }

  // 海岸线：沿最低节点下方弧过，契合"海湾"世界观
  const maxSvgY = sortedNodes.length > 0 ? Math.max(...sortedNodes.map((n) => n.svgY)) : SVG_H / 2;
  const coastY = Math.min(maxSvgY + 65, SVG_H - 15);
  const coastPath = `M -20 ${coastY + 25} C 160 ${coastY - 10} 360 ${coastY + 40} 560 ${coastY - 5} S 720 ${coastY + 15} 740 ${coastY}`;

  return { nodes: sortedNodes, links, movePaths, mainRoadPath, coastPath, heatConfig };
}

export function TownMap({
  world,
  agentNameMap,
  onLocationClick,
  onAgentClick,
  highlightedLocationId,
}: TownMapProps) {
  const [hoveredLabel, setHoveredLabel] = useState<string | null>(null);
  const [viewBox, setViewBox] = useState<ViewBox>({ x: 0, y: 0, width: SVG_W, height: SVG_H });
  const dragStateRef = useRef<{
    pointerId: number;
    startClientX: number;
    startClientY: number;
    originX: number;
    originY: number;
  } | null>(null);

  // 夜晚跳过检测
  const [showNightSkip, setShowNightSkip] = useState(false);
  const [nightSkipDay, setNightSkipDay] = useState(1);
  const prevClockRef = useRef<{ hour: number; day: number } | null>(null);

  useEffect(() => {
    const curr = world.world_clock;
    if (!curr) return;
    const prev = prevClockRef.current;
    if (prev !== null && prev.hour >= 21 && curr.hour <= 7 && curr.day > prev.day) {
      setNightSkipDay(curr.day);
      setShowNightSkip(true);
      const timer = setTimeout(() => setShowNightSkip(false), 4500);
      prevClockRef.current = { hour: curr.hour, day: curr.day };
      return () => clearTimeout(timer);
    }
    prevClockRef.current = { hour: curr.hour, day: curr.day };
  }, [world.world_clock]);

  const { nodes, links, movePaths, mainRoadPath, coastPath, heatConfig } = useMemo(() => buildMapData(world), [world]);

  // 昼夜循环效果
  const hour = world.world_clock?.hour ?? 12;
  const timeOfDay = getTimeOfDay(hour);
  const timeStyle = getTimeOfDayStyle(timeOfDay);

  const linkCoordinates = links
    .map((link) => {
      const source = nodes.find((node) => node.id === link.source);
      const target = nodes.find((node) => node.id === link.target);
      if (!source || !target) {
        return null;
      }
      return { ...link, source, target };
    })
    .filter(
      (
        link,
      ): link is {
        source: PositionedLocationNode;
        target: PositionedLocationNode;
      } & LocationLink => link !== null,
    );

  const setMapSummary = (label: string | null) => {
    setHoveredLabel(label);
  };

  const zoomMap = (factor: number, focusX = viewBox.x + viewBox.width / 2, focusY = viewBox.y + viewBox.height / 2) => {
    setViewBox((current) => {
      const nextWidth = current.width * factor;
      const nextHeight = (nextWidth / SVG_W) * SVG_H;
      const ratioX = (focusX - current.x) / current.width;
      const ratioY = (focusY - current.y) / current.height;
      const nextX = focusX - nextWidth * ratioX;
      const nextY = focusY - nextHeight * ratioY;
      return clampViewBox({ x: nextX, y: nextY, width: nextWidth, height: nextHeight });
    });
  };

  const resetView = () => {
    setViewBox({ x: 0, y: 0, width: SVG_W, height: SVG_H });
  };

  const handlePointerDown = (event: PointerEvent<SVGSVGElement>) => {
    const target = event.target as Element;
    if (target.closest("[data-map-interactive='true']")) {
      return;
    }

    dragStateRef.current = {
      pointerId: event.pointerId,
      startClientX: event.clientX,
      startClientY: event.clientY,
      originX: viewBox.x,
      originY: viewBox.y,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const handlePointerMove = (event: PointerEvent<SVGSVGElement>) => {
    const dragState = dragStateRef.current;
    if (!dragState || dragState.pointerId !== event.pointerId) {
      return;
    }

    const rect = event.currentTarget.getBoundingClientRect();
    if (!rect.width || !rect.height) {
      return;
    }

    const deltaX = ((event.clientX - dragState.startClientX) / rect.width) * viewBox.width;
    const deltaY = ((event.clientY - dragState.startClientY) / rect.height) * viewBox.height;

    setViewBox(clampViewBox({ x: dragState.originX - deltaX, y: dragState.originY - deltaY, width: viewBox.width, height: viewBox.height }));
  };

  const handlePointerEnd = (event: PointerEvent<SVGSVGElement>) => {
    if (dragStateRef.current?.pointerId === event.pointerId) {
      dragStateRef.current = null;
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  };

  const handleWheel = (event: WheelEvent<SVGSVGElement>) => {
    event.preventDefault();

    const rect = event.currentTarget.getBoundingClientRect();
    if (!rect.width || !rect.height) {
      return;
    }

    const pointerX = ((event.clientX - rect.left) / rect.width) * viewBox.width + viewBox.x;
    const pointerY = ((event.clientY - rect.top) / rect.height) * viewBox.height + viewBox.y;
    zoomMap(event.deltaY > 0 ? 1.12 : 0.88, pointerX, pointerY);
  };

  return (
    <div
      className={`flex h-full min-h-[460px] flex-col rounded-[28px] border p-4 shadow-xs backdrop-blur-sm transition-colors duration-1000 ${
        timeStyle.isDark
          ? "border-slate-700/50 bg-slate-800/80"
          : "border-white/70 bg-white/80"
      }`}
    >
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs uppercase tracking-[0.22em] text-moss">小镇地图</span>
          </div>
        </div>
        <div className={`flex flex-col items-end gap-1.5 text-xs ${timeStyle.isDark ? "text-slate-400" : "text-slate-500"}`}>
          {/* 热力等级 + 夜晚灯光 + 控制按钮 */}
          <div className="flex items-center gap-1.5">
            {/* 热力等级图例 - 背景色已说明状态，无需小圆点 */}
            <span className={`rounded-full px-2 py-0.5 ${
              timeStyle.isDark ? "bg-red-900/40 text-red-300" : "bg-red-50 text-red-700"
            }`}>
              非常活跃
            </span>
            <span className={`rounded-full px-2 py-0.5 ${
              timeStyle.isDark ? "bg-amber-900/40 text-amber-300" : "bg-amber-50 text-amber-700"
            }`}>
              较活跃
            </span>
            <span className={`rounded-full px-2 py-0.5 ${
              timeStyle.isDark ? "bg-emerald-900/40 text-emerald-300" : "bg-emerald-50 text-emerald-700"
            }`}>
              一般
            </span>
            {/* 夜晚灯格图例 */}
            {timeStyle.isDark && (
              <span className="rounded-sm bg-amber-100/20 px-2 py-0.5 font-mono text-amber-300">
                屋顶灯亮
              </span>
            )}
            {/* 分隔线 */}
            <span className={`h-3.5 w-px ${timeStyle.isDark ? "bg-slate-600" : "bg-slate-200"}`} />
            {/* 控制按钮 */}
            <button
              type="button"
              onClick={() => zoomMap(0.85)}
              className={`rounded-full border px-2 py-0.5 transition hover:border-moss hover:text-moss ${
                timeStyle.isDark
                  ? "border-slate-600 bg-slate-700 text-slate-300"
                  : "border-slate-200 bg-white text-slate-600"
              }`}
            >
              放大
            </button>
            <button
              type="button"
              onClick={() => zoomMap(1.15)}
              className={`rounded-full border px-2 py-0.5 transition hover:border-moss hover:text-moss ${
                timeStyle.isDark
                  ? "border-slate-600 bg-slate-700 text-slate-300"
                  : "border-slate-200 bg-white text-slate-600"
              }`}
            >
              缩小
            </button>
            <button
              type="button"
              onClick={resetView}
              className={`rounded-full border px-2 py-0.5 transition hover:border-moss hover:text-moss ${
                timeStyle.isDark
                  ? "border-slate-600 bg-slate-700 text-slate-300"
                  : "border-slate-200 bg-white text-slate-600"
              }`}
            >
              重置
            </button>
          </div>
        </div>
      </div>
      <div
        className={`relative min-h-0 flex-1 overflow-hidden rounded-[24px] border border-white/70 bg-linear-to-br ${timeStyle.bgGradient} transition-all duration-1000`}
      >
        {/* 夜晚遮罩层 */}
        {timeStyle.isDark && (
          <div
            className="pointer-events-none absolute inset-0 z-10 transition-opacity duration-1000"
            style={{ backgroundColor: timeStyle.overlayColor }}
          />
        )}
        {/* 夜晚跳过提示横幅 */}
        <AnimatePresence>
          {showNightSkip && (
            <motion.div
              key="night-skip-banner"
              initial={{ opacity: 0, y: -16 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -16 }}
              transition={{ duration: 0.4, ease: "easeOut" }}
              className="pointer-events-none absolute left-1/2 top-3 z-20 -translate-x-1/2"
            >
              <div className="flex items-center gap-2 rounded-full bg-slate-900/85 px-4 py-2 text-sm shadow-lg backdrop-blur-sm">
                <span className="text-base">🌙</span>
                <span className="text-slate-400">→</span>
                <span className="text-base">🌅</span>
                <span className="font-medium text-amber-300">夜晚已过，第 {nightSkipDay} 天开始</span>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
        <svg
          viewBox={`${viewBox.x} ${viewBox.y} ${viewBox.width} ${viewBox.height}`}
          className="h-full min-h-[420px] w-full touch-none"
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerEnd}
          onPointerCancel={handlePointerEnd}
          onWheel={handleWheel}
        >
          <defs>
            {/* Agent logo 裁剪（保留以防外部引用） */}
            <clipPath id="agentLogoClip">
              <circle cx="0" cy="0" r={11 * NODE_SCALE} />
            </clipPath>
          </defs>

          {/* 海岸像素带 — 硬边矩形，沿底部弧线模拟海湾 */}
          {coastPath && (
            <path
              d={coastPath}
              fill="none"
              stroke={timeStyle.isDark ? COAST_COLORS.night : COAST_COLORS.day}
              strokeWidth="18"
              strokeLinecap="square"
              strokeLinejoin="miter"
              opacity={timeStyle.isDark ? 0.5 : 0.7}
            />
          )}
          {/* 主街道 — 像素路砖段（虚线改为方形端点点阵） */}
          {mainRoadPath && (
            <path
              d={mainRoadPath}
              fill="none"
              stroke={timeStyle.isDark ? ROAD_COLORS.night.tile : ROAD_COLORS.day.tile}
              strokeWidth="10"
              strokeLinecap="square"
              strokeLinejoin="miter"
              strokeDasharray="12 6"
              opacity={0.85}
            />
          )}

          {linkCoordinates.map((link) => (
            <line
              key={`${link.source.id}-${link.target.id}`}
              x1={link.source.svgX}
              y1={link.source.svgY}
              x2={link.target.svgX}
              y2={link.target.svgY}
              stroke={timeStyle.isDark ? ROAD_COLORS.night.tileAlt : ROAD_COLORS.day.tileAlt}
              strokeWidth="3"
              strokeDasharray="4 6"
              strokeLinecap="square"
              opacity={0.65}
            />
          ))}

          <AnimatePresence>
            {movePaths.map((path, index) => (
              <motion.path
                key={path.id}
                d={`M ${path.fromX} ${path.fromY} Q ${(path.fromX + path.toX) / 2} ${(path.fromY + path.toY) / 2 - 22} ${path.toX} ${path.toY}`}
                fill="none"
                stroke="#10b981"
                strokeWidth="4"
                strokeLinecap="round"
                initial={{ pathLength: 0, opacity: 0 }}
                animate={{ pathLength: 1, opacity: [0, 0.55, 0] }}
                exit={{ opacity: 0 }}
                transition={{ duration: 2.2, delay: index * 0.1 }}
              />
            ))}
          </AnimatePresence>

          {nodes.map((node) => {
            const buildingStyle = getLocationBuildingStyle(node.type);
            const isHighlighted = node.id === highlightedLocationId;
            const heatLevel = getHeatLevel(node.heat, heatConfig);
            const glowThreshold = heatConfig?.glowThreshold ?? 0.1;
            const hasHeat = node.heat > glowThreshold;

            return (
              <g
                key={node.id}
                data-map-interactive="true"
                role="button"
                tabIndex={0}
                aria-label={`${node.name}，当前 ${node.occupantCount} / ${node.capacity} 人，${heatLevel.label}`}
                onMouseEnter={() => setMapSummary(`${node.name} · ${node.occupantCount}/${node.capacity} · ${heatLevel.label}`)}
                onMouseLeave={() => setMapSummary(null)}
                onFocus={() => setMapSummary(`${node.name} · ${node.occupantCount}/${node.capacity} · ${heatLevel.label}`)}
                onBlur={() => setMapSummary(null)}
                onClick={() => {
                  setMapSummary(`${node.name} · ${node.occupantCount}/${node.capacity} · ${heatLevel.label}`);
                  onLocationClick?.(node.id);
                }}
                onKeyDown={(event: KeyboardEvent<SVGGElement>) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    setMapSummary(`${node.name} · ${node.occupantCount}/${node.capacity} · ${heatLevel.label}`);
                    onLocationClick?.(node.id);
                  }
                }}
                className="cursor-pointer outline-hidden focus:outline-hidden"
              >
                <title>{`${node.name} · ${node.occupantCount}/${node.capacity} · ${heatLevel.label}`}</title>

                {/* 夜晚有人：屋顶后顶点小灯脉冲（建筑组件内已处理活跃灯，这里只做夜晚补充） */}
                {timeStyle.isDark && node.occupantCount > 0 && (
                  <motion.circle
                    cx={node.svgX}
                    cy={node.svgY - node.footprint.height - node.footprint.depth / 2 - 2}
                    r={2.5}
                    fill="#fbbf24"
                    stroke="#92400e"
                    strokeWidth={0.8}
                    initial={{ opacity: 0.4 }}
                    animate={{ opacity: [0.3, 1, 0.3] }}
                    transition={{ duration: 2.2, repeat: Infinity }}
                  />
                )}
                <WorldMapBuilding
                  centerX={node.svgX}
                  centerY={node.svgY}
                  footprint={node.footprint}
                  locationType={node.type}
                  name={node.name}
                  occupancyLabel={`${node.occupantCount}/${node.capacity} · ${buildingStyle.label}`}
                  isHighlighted={isHighlighted}
                  hasHeat={hasHeat}
                  heatScale={node.heat}
                  isDark={timeStyle.isDark}
                />

                {node.occupants.map((agent, index) => {
                  const position = getFrontArcPosition(
                    node.svgX,
                    node.svgY,
                    node.footprint,
                    index,
                    node.occupants.length,
                  );
                  const agentX = position.x;
                  const agentY = position.y;
                  const fill = agentColor(agent.id);
                  const label = agentNameMap[agent.id] ?? agent.name;
                  const hasLogo = !!agent.config_id;

                  return (
                    <g
                      key={agent.id}
                      data-map-interactive="true"
                      role="button"
                      tabIndex={0}
                      aria-label={`${label}，当前目标 ${agent.current_goal ?? "空闲中"}`}
                      onClick={(event) => {
                        event.stopPropagation();
                        setMapSummary(`${label} · ${agent.current_goal ?? "空闲中"}`);
                        onAgentClick?.(agent.id);
                      }}
                      onKeyDown={(event: KeyboardEvent<SVGGElement>) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          event.stopPropagation();
                          setMapSummary(`${label} · ${agent.current_goal ?? "空闲中"}`);
                          onAgentClick?.(agent.id);
                        }
                      }}
                      onMouseEnter={() => setMapSummary(`${label} · ${agent.current_goal ?? "空闲中"}`)}
                      onMouseLeave={() => setMapSummary(null)}
                      onFocus={() => setMapSummary(`${label} · ${agent.current_goal ?? "空闲中"}`)}
                      onBlur={() => setMapSummary(null)}
                      className="cursor-pointer"
                    >
                      <title>{`${label} · ${agent.current_goal ?? "空闲中"}`}</title>
                      <WorldMapAgent
                        x={agentX}
                        y={agentY - 14}
                        fill={fill}
                        label={label}
                        hasLogo={hasLogo}
                        configId={agent.config_id}
                        isDark={timeStyle.isDark}
                      />
                    </g>
                  );
                })}
              </g>
            );
          })}
        </svg>
        <div className={`pointer-events-none absolute inset-x-0 bottom-0 flex items-center justify-between gap-3 rounded-b-[24px] px-4 py-2 text-xs text-slate-400 ${
          timeStyle.isDark
            ? "bg-linear-to-t from-slate-900/80 to-transparent"
            : "bg-linear-to-t from-white/80 to-transparent"
        }`}>
          <p>点击地点查看详情。虚线框颜色表示活动热度。{timeStyle.isDark && "屋顶灯格亮起表示有人。"}</p>
          <p className={`shrink-0 text-right ${timeStyle.isDark ? "text-slate-400" : "text-slate-500"}`}>
            {hoveredLabel ?? "悬停、聚焦或点击后查看地点与居民摘要"}
          </p>
        </div>
      </div>
    </div>
  );
}
