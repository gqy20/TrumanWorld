"use client";

import { useMemo, useRef, useState, type KeyboardEvent, type PointerEvent, type WheelEvent } from "react";
import { AnimatePresence, motion } from "framer-motion";
import type { AgentSummary, WorldSnapshot } from "@/lib/types";
import { calculateLocationHeat, getHeatLevel, getTimeOfDay, getTimeOfDayStyle } from "@/lib/world-utils";

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

type ViewBox = {
  x: number;
  y: number;
  width: number;
  height: number;
};

const LOCATION_STYLES: Record<string, { icon: string; color: string; bgColor: string; label: string }> = {
  cafe: { icon: "☕", color: "#d97706", bgColor: "#fef3c7", label: "咖啡馆" },
  plaza: { icon: "🌳", color: "#0284c7", bgColor: "#e0f2fe", label: "广场" },
  park: { icon: "🌲", color: "#059669", bgColor: "#d1fae5", label: "公园" },
  shop: { icon: "🏪", color: "#7c3aed", bgColor: "#ede9fe", label: "商店" },
  home: { icon: "🏠", color: "#db2777", bgColor: "#fce7f3", label: "住宅" },
  office: { icon: "🏢", color: "#0369a1", bgColor: "#e0f2fe", label: "办公室" },
  default: { icon: "📍", color: "#64748b", bgColor: "#f8fafc", label: "地点" },
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
  const width = clamp(next.width, VIEWBOX_MIN_WIDTH, SVG_W);
  const height = (width / SVG_W) * SVG_H;
  const x = clamp(next.x, 0, SVG_W - width);
  const y = clamp(next.y, 0, SVG_H - height);

  return { x, y, width, height };
}

function buildMapData(world: WorldSnapshot) {
  const rawNodes: LocationNode[] = world.locations.map((location) => ({
    id: location.id,
    name: location.name,
    type: location.location_type,
    x: location.x,
    y: location.y,
    capacity: location.capacity,
    occupantCount: location.occupants.length,
    occupants: location.occupants,
    heat: calculateLocationHeat(location.id, world.recent_events),
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
    .filter((event) => event.event_type === "move" && event.location_id)
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

  return { nodes, links, movePaths };
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

  const { nodes, links, movePaths } = useMemo(() => buildMapData(world), [world]);

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
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45 }}
      className={`flex h-full min-h-[460px] flex-col rounded-[28px] border p-4 shadow-sm backdrop-blur transition-colors duration-1000 ${
        timeStyle.isDark 
          ? "border-slate-700/50 bg-slate-800/80" 
          : "border-white/70 bg-white/80"
      }`}
    >
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs uppercase tracking-[0.22em] text-moss">小镇地图</span>
            {/* 当前时段指示 */}
            <span className={`flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs ${
              timeStyle.isDark 
                ? "bg-slate-700 text-slate-200" 
                : "bg-slate-100 text-slate-600"
            }`}>
              <span>{timeStyle.icon}</span>
              <span>{timeStyle.label}</span>
              <span className="text-slate-400">
                {world.world_clock?.time ?? `${hour}:00`}
              </span>
            </span>
          </div>
          <p className={`mt-1 text-sm ${timeStyle.isDark ? "text-slate-400" : "text-slate-500"}`}>
            拖拽平移、滚轮缩放，点击地点查看详情。夜晚时有人的地点会亮灯。
          </p>
        </div>
        <div className={`flex flex-wrap items-center justify-end gap-2 text-xs ${timeStyle.isDark ? "text-slate-400" : "text-slate-500"}`}>
          {/* 地点类型图例 */}
          <span className={`flex items-center gap-1 rounded-full px-2.5 py-1 ${timeStyle.isDark ? "bg-slate-700" : "bg-slate-50"}`}>
            <span className="h-2 w-2 rounded-full bg-amber-500" />
            咖啡馆
          </span>
          <span className={`flex items-center gap-1 rounded-full px-2.5 py-1 ${timeStyle.isDark ? "bg-slate-700" : "bg-slate-50"}`}>
            <span className="h-2 w-2 rounded-full bg-sky-500" />
            广场
          </span>
          <span className={`flex items-center gap-1 rounded-full px-2.5 py-1 ${timeStyle.isDark ? "bg-slate-700" : "bg-slate-50"}`}>
            <span className="h-2 w-2 rounded-full bg-emerald-500" />
            公园
          </span>
          <span className={`flex items-center gap-1 rounded-full px-2.5 py-1 ${timeStyle.isDark ? "bg-slate-700" : "bg-slate-50"}`}>
            <span className="h-2 w-2 rounded-full bg-violet-500" />
            商店
          </span>
          <span className={`flex items-center gap-1 rounded-full px-2.5 py-1 ${timeStyle.isDark ? "bg-slate-700" : "bg-slate-50"}`}>
            <span className="h-2 w-2 rounded-full bg-pink-500" />
            住宅
          </span>
          {/* 分隔线 */}
          <span className={`h-4 w-px ${timeStyle.isDark ? "bg-slate-600" : "bg-slate-200"}`} />
          {/* 热力等级图例 */}
          <span className="flex items-center gap-1 rounded-full bg-red-50 px-2.5 py-1 text-red-700">
            <span className="h-2 w-2 animate-pulse rounded-full bg-red-500 shadow-sm shadow-red-400" />
            非常活跃
          </span>
          <span className="flex items-center gap-1 rounded-full bg-amber-50 px-2.5 py-1 text-amber-700">
            <span className="h-2 w-2 rounded-full bg-amber-500" />
            较活跃
          </span>
          <span className="flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-1 text-emerald-700">
            <span className="h-2 w-2 rounded-full bg-emerald-500" />
            一般
          </span>
          {/* 夜晚灯光图例 */}
          {timeStyle.isDark && (
            <>
              <span className={`h-4 w-px ${timeStyle.isDark ? "bg-slate-600" : "bg-slate-200"}`} />
              <span className="flex items-center gap-1 rounded-full bg-amber-100/50 px-2.5 py-1 text-amber-300">
                <span className="h-2 w-2 animate-pulse rounded-full bg-amber-400" />
                灯亮
              </span>
            </>
          )}
          {/* 控制按钮 */}
          <span className={`h-4 w-px ${timeStyle.isDark ? "bg-slate-600" : "bg-slate-200"}`} />
          <button
            type="button"
            onClick={() => zoomMap(0.85)}
            className={`rounded-full border px-2 py-1 transition hover:border-moss hover:text-moss ${
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
            className={`rounded-full border px-2 py-1 transition hover:border-moss hover:text-moss ${
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
            className={`rounded-full border px-2 py-1 transition hover:border-moss hover:text-moss ${
              timeStyle.isDark 
                ? "border-slate-600 bg-slate-700 text-slate-300" 
                : "border-slate-200 bg-white text-slate-600"
            }`}
          >
            重置
          </button>
        </div>
      </div>
      <div 
        className={`relative min-h-0 flex-1 overflow-hidden rounded-[24px] border border-white/70 bg-gradient-to-br ${timeStyle.bgGradient} transition-all duration-1000`}
      >
        {/* 夜晚遮罩层 */}
        {timeStyle.isDark && (
          <div 
            className="pointer-events-none absolute inset-0 z-10 transition-opacity duration-1000"
            style={{ backgroundColor: timeStyle.overlayColor }}
          />
        )}
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
            <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
              <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(148,163,184,0.12)" strokeWidth="1" />
            </pattern>
            <filter id="softShadow" x="-50%" y="-50%" width="200%" height="200%">
              <feDropShadow dx="0" dy="10" stdDeviation="8" floodColor="rgba(15,23,42,0.12)" />
            </filter>
            {/* 热力发光滤镜 */}
            <filter id="heatGlow" x="-100%" y="-100%" width="300%" height="300%">
              <feGaussianBlur stdDeviation="12" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            {/* 强热力发光滤镜 */}
            <filter id="heatGlowStrong" x="-150%" y="-150%" width="400%" height="400%">
              <feGaussianBlur stdDeviation="20" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            {/* Agent logo 圆形裁剪 */}
            <clipPath id="agentLogoClip">
              <circle cx="0" cy="0" r="11" />
            </clipPath>
          </defs>

          {/* 网格背景 - 根据昼夜调整颜色 */}
          <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
            <path 
              d="M 40 0 L 0 0 0 40" 
              fill="none" 
              stroke={timeStyle.isDark ? "rgba(148,163,184,0.06)" : "rgba(148,163,184,0.12)"} 
              strokeWidth="1" 
            />
          </pattern>
          <rect width={SVG_W} height={SVG_H} fill="url(#grid)" />
          {/* 装饰性路径 */}
          <path
            d="M 40 315 C 180 245, 270 255, 385 210 S 590 150, 670 190"
            fill="none"
            stroke={timeStyle.isDark ? "rgba(148,163,184,0.15)" : "rgba(148,163,184,0.3)"}
            strokeWidth="24"
            strokeLinecap="round"
          />
          <path
            d="M 120 90 C 245 110, 320 155, 485 110 S 620 90, 660 125"
            fill="none"
            stroke={timeStyle.isDark ? "rgba(255,255,255,0.2)" : "rgba(255,255,255,0.7)"}
            strokeWidth="12"
            strokeLinecap="round"
          />

          {linkCoordinates.map((link) => (
            <motion.line
              key={`${link.source.id}-${link.target.id}`}
              x1={link.source.svgX}
              y1={link.source.svgY}
              x2={link.target.svgX}
              y2={link.target.svgY}
              stroke="rgba(148,163,184,0.45)"
              strokeWidth="2"
              strokeDasharray="7 8"
              initial={{ pathLength: 0, opacity: 0 }}
              animate={{ pathLength: 1, opacity: 1 }}
              transition={{ duration: 0.6 }}
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
            const style = LOCATION_STYLES[node.type] ?? LOCATION_STYLES.default;
            const isHighlighted = node.id === highlightedLocationId;
            const outerRadius = 32 + node.capacity * 2.5;
            const heatLevel = getHeatLevel(node.heat);
            const hasHeat = node.heat > 0.15;

            return (
              <motion.g
                key={node.id}
                initial={{ opacity: 0, scale: 0.92 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ type: "spring", stiffness: 260, damping: 24 }}
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
                className="cursor-pointer"
              >
                <title>{`${node.name} · ${node.occupantCount}/${node.capacity} · ${heatLevel.label}`}</title>
                {/* 热力发光层 - 底层发光效果 */}
                {hasHeat && (
                  <motion.circle
                    cx={node.svgX}
                    cy={node.svgY}
                    r={outerRadius + 15 + node.heat * 20}
                    fill={heatLevel.glowColor}
                    filter={node.heat > 0.6 ? "url(#heatGlowStrong)" : "url(#heatGlow)"}
                    initial={{ opacity: 0 }}
                    animate={{ 
                      opacity: [0.4 + node.heat * 0.3, 0.6 + node.heat * 0.3, 0.4 + node.heat * 0.3],
                      scale: [1, 1.05, 1]
                    }}
                    transition={{ 
                      duration: 3 - node.heat, 
                      repeat: Infinity,
                      ease: "easeInOut"
                    }}
                    style={{ transformOrigin: `${node.svgX}px ${node.svgY}px` }}
                  />
                )}
                {/* 原有的外圈背景 */}
                <motion.circle
                  cx={node.svgX}
                  cy={node.svgY}
                  r={outerRadius}
                  fill={style.bgColor}
                  stroke={style.color}
                  strokeWidth={isHighlighted ? 4 : 2}
                  opacity={isHighlighted ? 0.5 : 0.3}
                  animate={isHighlighted ? { scale: [1, 1.06, 1] } : { scale: 1 }}
                  style={{ transformOrigin: `${node.svgX}px ${node.svgY}px` }}
                  transition={isHighlighted ? { duration: 1.8, repeat: Infinity } : { duration: 0.2 }}
                />
                {/* 热力指示环 - 围绕主节点 */}
                {hasHeat && (
                  <motion.circle
                    cx={node.svgX}
                    cy={node.svgY}
                    r={outerRadius + 8}
                    fill="none"
                    stroke={heatLevel.color}
                    strokeWidth={2 + node.heat * 2}
                    strokeDasharray={`${node.heat * 20} ${(1 - node.heat) * 20}`}
                    initial={{ opacity: 0, rotate: 0 }}
                    animate={{ 
                      opacity: 0.6 + node.heat * 0.4,
                      rotate: 360
                    }}
                    transition={{ 
                      rotate: { duration: 20, repeat: Infinity, ease: "linear" },
                      opacity: { duration: 0.5 }
                    }}
                    style={{ transformOrigin: `${node.svgX}px ${node.svgY}px` }}
                  />
                )}
                {/* 夜晚灯光效果 - 有人时发光 */}
                {timeStyle.isDark && node.occupantCount > 0 && (
                  <motion.circle
                    cx={node.svgX}
                    cy={node.svgY}
                    r={24}
                    fill="rgba(251, 191, 36, 0.3)"
                    filter="url(#heatGlow)"
                    initial={{ opacity: 0.3 }}
                    animate={{ opacity: [0.3, 0.6, 0.3] }}
                    transition={{ duration: 2, repeat: Infinity }}
                  />
                )}
                <circle
                  cx={node.svgX}
                  cy={node.svgY}
                  r={28}
                  fill={timeStyle.isDark ? "rgba(30, 41, 59, 0.95)" : "rgba(255,255,255,0.96)"}
                  stroke={style.color}
                  strokeWidth={isHighlighted ? 5 : 3}
                  filter="url(#softShadow)"
                />
                {/* 夜晚窗户灯光 */}
                {timeStyle.isDark && node.occupantCount > 0 && (
                  <>
                    <rect
                      x={node.svgX - 8}
                      y={node.svgY - 6}
                      width={6}
                      height={6}
                      fill="rgba(251, 191, 36, 0.8)"
                      rx={1}
                    />
                    <rect
                      x={node.svgX + 2}
                      y={node.svgY - 6}
                      width={6}
                      height={6}
                      fill="rgba(251, 191, 36, 0.6)"
                      rx={1}
                    />
                  </>
                )}
                <text x={node.svgX} y={node.svgY + 8} textAnchor="middle" fontSize="24">
                  {style.icon}
                </text>
                <text
                  x={node.svgX}
                  y={node.svgY + outerRadius + 22}
                  textAnchor="middle"
                  fontSize="13"
                  fontWeight="700"
                  fill="#334155"
                >
                  {node.name}
                </text>

                {node.occupantCount > 0 ? (
                  <>
                    <circle
                      cx={node.svgX + 22}
                      cy={node.svgY - 20}
                      r={12}
                      fill="#ef4444"
                      stroke="white"
                      strokeWidth={3}
                    />
                    <text
                      x={node.svgX + 22}
                      y={node.svgY - 16}
                      textAnchor="middle"
                      fontSize="10"
                      fontWeight="700"
                      fill="white"
                    >
                      {node.occupantCount}
                    </text>
                  </>
                ) : null}

                {node.occupants.map((agent, index) => {
                  const ringRadius = outerRadius + 22;
                  const angle =
                    (index / Math.max(node.occupants.length, 1)) * Math.PI * 2 - Math.PI / 2;
                  const agentX = node.svgX + Math.cos(angle) * ringRadius;
                  const agentY = node.svgY + Math.sin(angle) * ringRadius;
                  const fill = agentColor(agent.id);
                  const label = agentNameMap[agent.id] ?? agent.name;
                  // 如果有自定义 logo，使用 logo；否则显示首字母
                  const hasLogo = agent.config_id && ["truman", "spouse", "friend", "neighbor", "alice"].includes(agent.config_id);

                  return (
                    <motion.g
                      key={agent.id}
                      initial={{ opacity: 0, scale: 0.8 }}
                      animate={{ opacity: 1, scale: 1 }}
                      transition={{ type: "spring", stiffness: 320, damping: 22, delay: index * 0.03 }}
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
                      <circle
                        cx={agentX}
                        cy={agentY}
                        r={16}
                        fill="rgba(255,255,255,0.92)"
                        stroke={fill}
                        strokeWidth={4}
                        filter="url(#softShadow)"
                      />
                      {hasLogo ? (
                        // 使用自定义 logo
                        <>
                          <g transform={`translate(${agentX}, ${agentY})`} clipPath="url(#agentLogoClip)">
                            <image
                              href={`/agents/${agent.config_id}.svg`}
                              x={-11}
                              y={-11}
                              width={22}
                              height={22}
                            />
                          </g>
                          <circle
                            cx={agentX}
                            cy={agentY}
                            r={11}
                            fill="none"
                            stroke={fill}
                            strokeWidth={2}
                            opacity={0.5}
                          />
                        </>
                      ) : (
                        // 默认显示首字母
                        <>
                          <circle cx={agentX} cy={agentY} r={11} fill={fill} opacity={0.9} />
                          <text
                            x={agentX}
                            y={agentY + 4}
                            textAnchor="middle"
                            fontSize="10"
                            fontWeight="700"
                            fill="white"
                          >
                            {label.charAt(0).toUpperCase()}
                          </text>
                        </>
                      )}
                    </motion.g>
                  );
                })}
              </motion.g>
            );
          })}
        </svg>
        <div className={`pointer-events-none absolute inset-x-0 bottom-0 flex items-center justify-between gap-3 rounded-b-[24px] px-4 py-2 text-xs text-slate-400 ${
          timeStyle.isDark 
            ? "bg-gradient-to-t from-slate-900/80 to-transparent" 
            : "bg-gradient-to-t from-white/80 to-transparent"
        }`}>
          <p>点击地点查看详情。光晕强度表示活动热度。{timeStyle.isDark && "黄色窗户表示有人。"}</p>
          <p className={`flex-shrink-0 text-right ${timeStyle.isDark ? "text-slate-400" : "text-slate-500"}`}>
            {hoveredLabel ?? "悬停、聚焦或点击后查看地点与居民摘要"}
          </p>
        </div>
      </div>
    </motion.div>
  );
}
