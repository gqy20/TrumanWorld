"use client";

import { useEffect, useMemo, useRef, useState, type KeyboardEvent, type MouseEvent, type PointerEvent, type WheelEvent } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { EVENT_MOVE } from "@/lib/simulation-protocol";
import type { AgentSummary, WorldSnapshot } from "@/lib/types";
import { buildHeatGlowMotionProps, buildHeatRingMotionProps } from "@/lib/world-map-motion";
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

const LOCATION_STYLES: Record<string, { icon: string; color: string; bgColor: string; label: string }> = {
  cafe: { icon: "☕", color: "#d97706", bgColor: "#fef3c7", label: "咖啡馆" },
  plaza: { icon: "🌳", color: "#0284c7", bgColor: "#e0f2fe", label: "广场" },
  park: { icon: "🌲", color: "#059669", bgColor: "#d1fae5", label: "公园" },
  shop: { icon: "🏪", color: "#7c3aed", bgColor: "#ede9fe", label: "商场" },
  home: { icon: "🏠", color: "#db2777", bgColor: "#fce7f3", label: "住宅" },
  office: { icon: "🏢", color: "#0369a1", bgColor: "#e0f2fe", label: "办公室" },
  hospital: { icon: "🏥", color: "#dc2626", bgColor: "#fee2e2", label: "医院" },
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
  const width = clamp(next.width, VIEWBOX_MIN_WIDTH, VIEWBOX_MAX_WIDTH);
  const height = (width / SVG_W) * SVG_H;
  const x = clamp(next.x, -(width - SVG_W) / 2, SVG_W - width / 2);
  const y = clamp(next.y, -(height - SVG_H) / 2, SVG_H - height / 2);

  return { x, y, width, height };
}

// ─── 小地图常量 ───────────────────────────────────────────────
const MM_W = 160;
const MM_H = 100;
const MM_PAD = 12;

interface MiniMapProps {
  nodes: PositionedLocationNode[];
  links: LocationLink[];
  viewBox: ViewBox;
  isDark: boolean;
  onNavigate: (svgX: number, svgY: number) => void;
}

function MiniMap({ nodes, links, viewBox, isDark, onNavigate }: MiniMapProps) {
  const mmDragRef = useRef<{ startX: number; startY: number; startVbX: number; startVbY: number } | null>(null);

  // SVG坐标 → 小地图坐标
  const toMM = (svgX: number, svgY: number) => ({
    x: MM_PAD + ((svgX / SVG_W) * (MM_W - MM_PAD * 2)),
    y: MM_PAD + ((svgY / SVG_H) * (MM_H - MM_PAD * 2)),
  });

  // 小地图坐标 → SVG坐标
  const toSVG = (mmX: number, mmY: number) => ({
    x: ((mmX - MM_PAD) / (MM_W - MM_PAD * 2)) * SVG_W,
    y: ((mmY - MM_PAD) / (MM_H - MM_PAD * 2)) * SVG_H,
  });

  // 视口框在小地图中的位置
  const frameX = MM_PAD + (viewBox.x / SVG_W) * (MM_W - MM_PAD * 2);
  const frameY = MM_PAD + (viewBox.y / SVG_H) * (MM_H - MM_PAD * 2);
  const frameW = (viewBox.width / SVG_W) * (MM_W - MM_PAD * 2);
  const frameH = (viewBox.height / SVG_H) * (MM_H - MM_PAD * 2);

  const bgColor = isDark ? "rgba(15,23,42,0.88)" : "rgba(255,255,255,0.88)";
  const borderColor = isDark ? "rgba(100,116,139,0.5)" : "rgba(148,163,184,0.4)";
  const linkColor = isDark ? "rgba(100,116,139,0.3)" : "rgba(148,163,184,0.4)";

  const handleClick = (e: MouseEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const mmX = ((e.clientX - rect.left) / rect.width) * MM_W;
    const mmY = ((e.clientY - rect.top) / rect.height) * MM_H;
    const { x, y } = toSVG(mmX, mmY);
    onNavigate(x, y);
  };

  // 拖拽视口框
  const handleFramePointerDown = (e: PointerEvent<SVGRectElement>) => {
    e.stopPropagation();
    mmDragRef.current = { startX: e.clientX, startY: e.clientY, startVbX: viewBox.x, startVbY: viewBox.y };
    e.currentTarget.setPointerCapture(e.pointerId);
  };
  const handleFramePointerMove = (e: PointerEvent<SVGRectElement>) => {
    if (!mmDragRef.current) return;
    e.stopPropagation();
    const rect = (e.currentTarget.closest("svg") as SVGSVGElement)?.getBoundingClientRect();
    if (!rect) return;
    const dxPx = e.clientX - mmDragRef.current.startX;
    const dyPx = e.clientY - mmDragRef.current.startY;
    const dxSvg = (dxPx / rect.width) * MM_W * (SVG_W / (MM_W - MM_PAD * 2));
    const dySvg = (dyPx / rect.height) * MM_H * (SVG_H / (MM_H - MM_PAD * 2));
    onNavigate(mmDragRef.current.startVbX + dxSvg + viewBox.width / 2, mmDragRef.current.startVbY + dySvg + viewBox.height / 2);
  };
  const handleFramePointerUp = (e: PointerEvent<SVGRectElement>) => {
    mmDragRef.current = null;
    e.currentTarget.releasePointerCapture(e.pointerId);
  };

  return (
    <svg
      width={MM_W}
      height={MM_H}
      viewBox={`0 0 ${MM_W} ${MM_H}`}
      onClick={handleClick}
      className="cursor-crosshair"
    >
      {/* 背景 */}
      <rect x={0} y={0} width={MM_W} height={MM_H} fill={bgColor} stroke={borderColor} strokeWidth={1} />

      {/* 连线 */}
      {links.map((link) => {
        const s = nodes.find((n) => n.id === link.source);
        const t = nodes.find((n) => n.id === link.target);
        if (!s || !t) return null;
        const sp = toMM(s.svgX, s.svgY);
        const tp = toMM(t.svgX, t.svgY);
        return (
          <line key={`mm-${link.source}-${link.target}`}
            x1={sp.x} y1={sp.y} x2={tp.x} y2={tp.y}
            stroke={linkColor} strokeWidth={0.8} />
        );
      })}

      {/* 地点圆点 */}
      {nodes.map((node) => {
        const { x, y } = toMM(node.svgX, node.svgY);
        const style = LOCATION_STYLES[node.type] ?? LOCATION_STYLES.default;
        const hasOccupants = node.occupantCount > 0;
        return (
          <g key={`mm-node-${node.id}`}>
            {/* 热力光晕（有人时显示） */}
            {hasOccupants && (
              <circle cx={x} cy={y} r={7} fill={style.color} opacity={0.15} />
            )}
            <circle
              cx={x} cy={y} r={hasOccupants ? 4.5 : 3}
              fill={hasOccupants ? style.color : (isDark ? "#475569" : "#94a3b8")}
              stroke={isDark ? "rgba(15,23,42,0.6)" : "rgba(255,255,255,0.8)"}
              strokeWidth={1}
            />
            {/* 有人数时显示小计数徽章 */}
            {node.occupantCount > 0 && (
              <text x={x + 5} y={y - 4}
                fontSize={5} fontWeight="700"
                fill={isDark ? "#94a3b8" : "#64748b"}
                textAnchor="start">
                {node.occupantCount}
              </text>
            )}
          </g>
        );
      })}

      {/* 视口指示框 */}
      <rect
        x={frameX} y={frameY} width={Math.max(frameW, 4)} height={Math.max(frameH, 4)}
        fill="rgba(59,130,246,0.08)"
        stroke="rgba(59,130,246,0.7)"
        strokeWidth={1.2}
        rx={2}
        className="cursor-move"
        onPointerDown={handleFramePointerDown}
        onPointerMove={handleFramePointerMove}
        onPointerUp={handleFramePointerUp}
        onPointerCancel={handleFramePointerUp}
        onClick={(e) => e.stopPropagation()}
      />
    </svg>
  );
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

  // 动态装饰路径
  const homeNode = nodes.find((n) => n.type === "home");
  const plazaNode = nodes.find((n) => n.type === "plaza");
  const officeNode = nodes.find((n) => n.type === "office");

  // 主街道：经过住宅 -> 广场 -> 办公室，用二次贝塞尔穿过三点
  let mainRoadPath = "";
  if (homeNode && plazaNode && officeNode) {
    // 以广场为控制点，让曲线自然弯曲穿过三个节点区域
    const cpX = plazaNode.svgX;
    const cpY = plazaNode.svgY;
    mainRoadPath = `M ${homeNode.svgX} ${homeNode.svgY} Q ${cpX} ${cpY} ${officeNode.svgX} ${officeNode.svgY}`;
  }

  // 海岸线：沿最低节点下方弧过，契合"海湾"世界观
  const maxSvgY = nodes.length > 0 ? Math.max(...nodes.map((n) => n.svgY)) : SVG_H / 2;
  const coastY = Math.min(maxSvgY + 65, SVG_H - 15);
  const coastPath = `M -20 ${coastY + 25} C 160 ${coastY - 10} 360 ${coastY + 40} 560 ${coastY - 5} S 720 ${coastY + 15} 740 ${coastY}`;

  return { nodes, links, movePaths, mainRoadPath, coastPath, heatConfig };
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
  const [miniMapCollapsed, setMiniMapCollapsed] = useState(false);
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

  // 对话气泡：agentId -> { message, key }（key 用于触发重新动画）
  const [speechBubbles, setSpeechBubbles] = useState<Record<string, { message: string; key: number }>>({});
  const bubbleTimersRef = useRef<Record<string, ReturnType<typeof setTimeout>>>({});
  const prevEventIdsRef = useRef<Set<string>>(new Set());

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

  // 检测新的 speech/talk 事件，更新对话气泡
  useEffect(() => {
    const speechEvents = world.recent_events.filter(
      (e) => (e.event_type === "speech" || e.event_type === "talk") && e.actor_agent_id,
    );

    const newBubbles: Record<string, { message: string; key: number }> = {};
    for (const event of speechEvents) {
      const agentId = event.actor_agent_id!;
      const message = typeof event.payload.message === "string" ? event.payload.message : null;
      if (!message) continue;
      // 只处理新出现的事件（避免世界快照刷新时重复触发）
      if (prevEventIdsRef.current.has(event.id)) continue;
      newBubbles[agentId] = { message, key: Date.now() };
    }

    // 更新 prevEventIds
    prevEventIdsRef.current = new Set(world.recent_events.map((e) => e.id));

    if (Object.keys(newBubbles).length === 0) return;

    const MAX_BUBBLES = 4;

    setSpeechBubbles((prev) => {
      const next = { ...prev };
      for (const [agentId, bubble] of Object.entries(newBubbles)) {
        next[agentId] = bubble;
        // 清除旧定时器
        if (bubbleTimersRef.current[agentId]) {
          clearTimeout(bubbleTimersRef.current[agentId]);
        }
        // 6 秒后自动消失
        bubbleTimersRef.current[agentId] = setTimeout(() => {
          setSpeechBubbles((cur) => {
            const updated = { ...cur };
            delete updated[agentId];
            return updated;
          });
          delete bubbleTimersRef.current[agentId];
        }, 6000);
      }
      // 超过数量上限时，移除 key 最小（最旧）的气泡
      const entries = Object.entries(next);
      if (entries.length > MAX_BUBBLES) {
        entries.sort((a, b) => a[1].key - b[1].key);
        const toRemove = entries.slice(0, entries.length - MAX_BUBBLES);
        for (const [id] of toRemove) {
          delete next[id];
          if (bubbleTimersRef.current[id]) {
            clearTimeout(bubbleTimersRef.current[id]);
            delete bubbleTimersRef.current[id];
          }
        }
      }
      return next;
    });
  }, [world.recent_events]);

  useEffect(() => {
    return () => {
      for (const timer of Object.values(bubbleTimersRef.current)) {
        clearTimeout(timer);
      }
      bubbleTimersRef.current = {};
    };
  }, []);

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

  // 小地图点击/拖拽导航：以 SVG 坐标为中心，保持当前缩放级别
  const focusOnSvgPoint = (svgX: number, svgY: number) => {
    setViewBox((current) =>
      clampViewBox({
        x: svgX - current.width / 2,
        y: svgY - current.height / 2,
        width: current.width,
        height: current.height,
      }),
    );
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
      className={`relative flex h-full min-h-[460px] flex-col rounded-[28px] border p-4 shadow-xs backdrop-blur-sm transition-colors duration-1000 ${
        timeStyle.isDark
          ? "border-slate-700/50 bg-slate-800/80"
          : "border-white/70 bg-white/80"
      }`}
    >
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div />
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
            {/* 夜晚灯光图例 */}
            {timeStyle.isDark && (
              <span className="rounded-full bg-amber-100/20 px-2 py-0.5 text-amber-300">
                灯亮
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
      {/* 小地图 - 贴着内层地图容器左上角（外层定位，不受 overflow-hidden 裁切） */}
      <div className="absolute left-4 top-4 z-30">
        <AnimatePresence mode="wait">
          {miniMapCollapsed ? (
            /* 折叠态：只显示一个贴边小图标 */
            <motion.button
              key="mm-collapsed"
              type="button"
              onClick={() => setMiniMapCollapsed(false)}
              title="展开小地图"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
              className={`flex h-7 w-7 items-center justify-center rounded-br-lg border-b border-r text-[11px] shadow-sm transition-colors hover:scale-105 ${
                timeStyle.isDark
                  ? "border-slate-600 bg-slate-800/90 text-slate-300 hover:bg-slate-700/90"
                  : "border-slate-200 bg-white/90 text-slate-500 hover:bg-white"
              }`}
            >
              🗺
            </motion.button>
          ) : (
            /* 展开态：小地图 + 右下角关闭按钮 */
            <motion.div
              key="mm-open"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              transition={{ duration: 0.18 }}
              className="relative"
            >
              <div className={`overflow-hidden rounded-br-[10px] shadow-lg ring-1 backdrop-blur-sm ${
                timeStyle.isDark ? "ring-slate-600/50" : "ring-slate-200/80"
              }`}>
                <MiniMap
                  nodes={nodes}
                  links={links}
                  viewBox={viewBox}
                  isDark={timeStyle.isDark}
                  onNavigate={focusOnSvgPoint}
                />
              </div>
              {/* 关闭按钮：右下角角标 */}
              <button
                type="button"
                onClick={() => setMiniMapCollapsed(true)}
                title="折叠小地图"
                className={`absolute bottom-0 right-0 flex h-5 w-5 items-center justify-center rounded-tl-md border-l border-t text-[9px] transition-colors ${
                  timeStyle.isDark
                    ? "border-slate-600 bg-slate-800/90 text-slate-400 hover:text-slate-200"
                    : "border-slate-200 bg-white/90 text-slate-400 hover:text-slate-600"
                }`}
              >
                ×
              </button>
            </motion.div>
          )}
        </AnimatePresence>
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
              <circle cx="0" cy="0" r={11 * NODE_SCALE} />
            </clipPath>
          </defs>

          {/* 海岸线装饰 - 沿最低节点下方弧过，蓝色半透明 */}
          {coastPath && (
            <path
              d={coastPath}
              fill="none"
              stroke={timeStyle.isDark ? "rgba(147,197,253,0.12)" : "rgba(147,197,253,0.35)"}
              strokeWidth="32"
              strokeLinecap="round"
            />
          )}
          {/* 主街道 - 动态穿过住宅 -> 广场 -> 办公室 */}
          {mainRoadPath && (
            <path
              d={mainRoadPath}
              fill="none"
              stroke={timeStyle.isDark ? "rgba(148,163,184,0.12)" : "rgba(148,163,184,0.28)"}
              strokeWidth="20"
              strokeLinecap="round"
            />
          )}

          {linkCoordinates.map((link) => (
            <line
              key={`${link.source.id}-${link.target.id}`}
              x1={link.source.svgX}
              y1={link.source.svgY}
              x2={link.target.svgX}
              y2={link.target.svgY}
              stroke="rgba(148,163,184,0.45)"
              strokeWidth="2"
              strokeDasharray="7 8"
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
            const outerRadius = (32 + node.capacity * 2.5) * NODE_SCALE;
            const heatLevel = getHeatLevel(node.heat, heatConfig);
            const glowThreshold = heatConfig?.glowThreshold ?? 0.1;
            const hasHeat = node.heat > glowThreshold;
            const heatGlowMotion = buildHeatGlowMotionProps(node.heat);
            const heatRingMotion = buildHeatRingMotionProps(node.heat);

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
                {/* 热力发光层 - 底层发光效果 */}
                {hasHeat && (
                  <motion.circle
                    cx={node.svgX}
                    cy={node.svgY}
                    r={outerRadius + 15 * NODE_SCALE + node.heat * 20 * NODE_SCALE}
                    fill={heatLevel.glowColor}
                    filter={node.heat > 0.6 ? "url(#heatGlowStrong)" : "url(#heatGlow)"}
                    initial={heatGlowMotion.initial}
                    animate={heatGlowMotion.animate}
                    transition={heatGlowMotion.transition}
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
                    r={outerRadius + 8 * NODE_SCALE}
                    fill="none"
                    stroke={heatLevel.color}
                    strokeWidth={2 + node.heat * 2}
                    strokeDasharray={`${node.heat * 20} ${(1 - node.heat) * 20}`}
                    initial={heatRingMotion.initial}
                    animate={heatRingMotion.animate}
                    transition={heatRingMotion.transition}
                    style={{ transformOrigin: `${node.svgX}px ${node.svgY}px` }}
                  />
                )}
                {/* 夜晚灯光效果 - 有人时发光 */}
                {timeStyle.isDark && node.occupantCount > 0 && (
                  <motion.circle
                    cx={node.svgX}
                    cy={node.svgY}
                    r={24 * NODE_SCALE}
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
                  r={28 * NODE_SCALE}
                  fill={timeStyle.isDark ? "rgba(30, 41, 59, 0.95)" : "rgba(255,255,255,0.96)"}
                  stroke={style.color}
                  strokeWidth={isHighlighted ? 5 : 3}
                  filter="url(#softShadow)"
                />
                {/* 夜晚窗户灯光 */}
                {timeStyle.isDark && node.occupantCount > 0 && (
                  <>
                    <rect
                      x={node.svgX - 8 * NODE_SCALE}
                      y={node.svgY - 6 * NODE_SCALE}
                      width={6 * NODE_SCALE}
                      height={6 * NODE_SCALE}
                      fill="rgba(251, 191, 36, 0.8)"
                      rx={1}
                    />
                    <rect
                      x={node.svgX + 2 * NODE_SCALE}
                      y={node.svgY - 6 * NODE_SCALE}
                      width={6 * NODE_SCALE}
                      height={6 * NODE_SCALE}
                      fill="rgba(251, 191, 36, 0.6)"
                      rx={1}
                    />
                  </>
                )}
                <text x={node.svgX} y={node.svgY + 8 * NODE_SCALE} textAnchor="middle" fontSize={24 * NODE_SCALE}>
                  {style.icon}
                </text>
                <text
                  x={node.svgX}
                  y={node.svgY + outerRadius + 22 * NODE_SCALE}
                  textAnchor="middle"
                  fontSize={13 * NODE_SCALE}
                  fontWeight="700"
                  fill="#334155"
                >
                  {node.name}
                </text>

                {node.occupantCount > 0 ? (
                  <>
                    <circle
                      cx={node.svgX + 22 * NODE_SCALE}
                      cy={node.svgY - 20 * NODE_SCALE}
                      r={12 * NODE_SCALE}
                      fill="#ef4444"
                      stroke="white"
                      strokeWidth={3}
                    />
                    <text
                      x={node.svgX + 22 * NODE_SCALE}
                      y={node.svgY - 16 * NODE_SCALE}
                      textAnchor="middle"
                      fontSize={10 * NODE_SCALE}
                      fontWeight="700"
                      fill="white"
                    >
                      {node.occupantCount}
                    </text>
                  </>
                ) : null}

                {node.occupants.map((agent, index) => {
                  // agent 头像只分布在上半圆（避开下方的地点名称）
                  // 角度范围：-150° 到 150°（避开下方 60° 区域）
                  const ringRadius = outerRadius + 22 * NODE_SCALE;
                  const totalAgents = node.occupants.length;
                  const startAngle = (-150 * Math.PI) / 180;
                  const endAngle = (150 * Math.PI) / 180;
                  // 单个 agent 时放在正上方，多个时均匀分布在上半圆
                  const angle = totalAgents === 1
                    ? -Math.PI / 2  // 正上方
                    : startAngle + (index / (totalAgents - 1)) * (endAngle - startAngle);
                  const agentX = node.svgX + Math.cos(angle) * ringRadius;
                  const agentY = node.svgY + Math.sin(angle) * ringRadius;
                  const fill = agentColor(agent.id);
                  const label = agentNameMap[agent.id] ?? agent.name;
                  // 只要有 config_id 就尝试加载 /agents/{config_id}.svg
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
                      <circle
                        cx={agentX}
                        cy={agentY}
                        r={16 * NODE_SCALE}
                        fill="rgba(255,255,255,0.92)"
                        stroke={fill}
                        strokeWidth={4 * NODE_SCALE}
                        filter="url(#softShadow)"
                      />
                      {hasLogo ? (
                        // 使用自定义 logo
                        <>
                          <g transform={`translate(${agentX}, ${agentY})`} clipPath="url(#agentLogoClip)">
                            <image
                              href={`/agents/${agent.config_id}.svg`}
                              x={-11 * NODE_SCALE}
                              y={-11 * NODE_SCALE}
                              width={22 * NODE_SCALE}
                              height={22 * NODE_SCALE}
                            />
                          </g>
                          <circle
                            cx={agentX}
                            cy={agentY}
                            r={11 * NODE_SCALE}
                            fill="none"
                            stroke={fill}
                            strokeWidth={2}
                            opacity={0.5}
                          />
                        </>
                      ) : (
                        // 默认显示首字母
                        <>
                          <circle cx={agentX} cy={agentY} r={11 * NODE_SCALE} fill={fill} opacity={0.9} />
                          <text
                            x={agentX}
                            y={agentY + 4 * NODE_SCALE}
                            textAnchor="middle"
                            fontSize={10 * NODE_SCALE}
                            fontWeight="700"
                            fill="white"
                          >
                            {label.charAt(0).toUpperCase()}
                          </text>
                        </>
                      )}
                      {/* 对话气泡 */}
                      {speechBubbles[agent.id] && (() => {
                        const bubble = speechBubbles[agent.id];
                        const maxChars = 28;
                        const displayMsg = bubble.message.length > maxChars
                          ? `${bubble.message.slice(0, maxChars)}…`
                          : bubble.message;
                        const bubbleW = 120;
                        const bubbleH = 36;
                        const TAIL_H = 8;
                        const MARGIN = 6; // SVG 边界安全距离

                        // 1. 边界夹紧：防止气泡超出 SVG 画布左右边界
                        const rawBubbleX = agentX - bubbleW / 2;
                        const clampedBubbleX = Math.max(MARGIN, Math.min(rawBubbleX, SVG_W - bubbleW - MARGIN));
                        // 尖角中心始终对准 agent，但也夹紧在气泡 x 范围内
                        const tailCX = Math.max(clampedBubbleX + 8, Math.min(agentX, clampedBubbleX + bubbleW - 8));

                        // 2. 上下翻转：agent 太靠上时气泡显示在下方
                        const spaceAbove = agentY - viewBox.y;
                        const showBelow = spaceAbove < bubbleH + TAIL_H + 20;
                        const bubbleY = showBelow
                          ? agentY + 16 * NODE_SCALE + TAIL_H + 4
                          : agentY - 16 * NODE_SCALE - bubbleH - TAIL_H - 4;

                        const bgColor = timeStyle.isDark ? "rgba(30,41,59,0.96)" : "rgba(255,255,255,0.96)";
                        const textColor = timeStyle.isDark ? "#e2e8f0" : "#1e293b";

                        // 尖角三角形坐标（朝向 agent 方向）
                        const tailPoints = showBelow
                          ? `${tailCX - 5},${bubbleY} ${tailCX + 5},${bubbleY} ${tailCX},${bubbleY - TAIL_H}`
                          : `${tailCX - 5},${bubbleY + bubbleH} ${tailCX + 5},${bubbleY + bubbleH} ${tailCX},${bubbleY + bubbleH + TAIL_H}`;

                        return (
                          <motion.g
                            key={bubble.key}
                            initial={{ opacity: 0, y: showBelow ? -4 : 4 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: showBelow ? -4 : 4 }}
                            transition={{ duration: 0.3 }}
                          >
                            {/* 气泡背景 */}
                            <rect
                              x={clampedBubbleX}
                              y={bubbleY}
                              width={bubbleW}
                              height={bubbleH}
                              rx={10}
                              fill={bgColor}
                              stroke={fill}
                              strokeWidth={1.5}
                              filter="url(#softShadow)"
                            />
                            {/* 气泡尖角 */}
                            <polygon
                              points={tailPoints}
                              fill={bgColor}
                              stroke={fill}
                              strokeWidth={1.5}
                            />
                            {/* 遮住尖角与气泡接缝 */}
                            <rect
                              x={tailCX - 5}
                              y={showBelow ? bubbleY - 2 : bubbleY + bubbleH - 2}
                              width={10}
                              height={4}
                              fill={bgColor}
                            />
                            {/* 对话文字 */}
                            <foreignObject
                              x={clampedBubbleX + 6}
                              y={bubbleY + 4}
                              width={bubbleW - 12}
                              height={bubbleH - 8}
                            >
                              <div
                                // @ts-expect-error xmlns required for SVG foreignObject
                                xmlns="http://www.w3.org/1999/xhtml"
                                style={{
                                  fontSize: "9px",
                                  lineHeight: "1.3",
                                  color: textColor,
                                  wordBreak: "break-all",
                                  overflow: "hidden",
                                  display: "-webkit-box",
                                  WebkitLineClamp: 2,
                                  WebkitBoxOrient: "vertical",
                                }}
                              >
                                💬 {displayMsg}
                              </div>
                            </foreignObject>
                          </motion.g>
                        );
                      })()}
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
          <p>点击地点查看详情。光晕强度表示活动热度。{timeStyle.isDark && "黄色窗户表示有人。"}</p>
          <p className={`shrink-0 text-right ${timeStyle.isDark ? "text-slate-400" : "text-slate-500"}`}>
            {hoveredLabel ?? "悬停、聚焦或点击后查看地点与居民摘要"}
          </p>
        </div>
      </div>
    </div>
  );
}
