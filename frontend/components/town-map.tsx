"use client";

import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import type { WorldSnapshot } from "@/lib/types";
import { getTimeOfDay, getTimeOfDayStyle } from "@/lib/world-utils";
import { TownLocationNode } from "./town-location-node";
import { MiniMap } from "./town-mini-map";
import {
  NODE_SCALE,
  buildMapData,
  type LocationLink,
  type PositionedLocationNode,
} from "./town-map-utils";
import { useNightSkipBanner } from "./use-night-skip-banner";
import { useSpeechBubbles } from "./use-speech-bubbles";
import { useTownMapViewport } from "./use-town-map-viewport";

interface TownMapProps {
  world: WorldSnapshot;
  agentNameMap: Record<string, string>;
  onLocationClick?: (locationId: string) => void;
  onAgentClick?: (agentId: string) => void;
  highlightedLocationId?: string | null;
}

export function TownMap({
  world,
  agentNameMap,
  onLocationClick,
  onAgentClick,
  highlightedLocationId,
}: TownMapProps) {
  const [hoveredLabel, setHoveredLabel] = useState<string | null>(null);
  const [miniMapCollapsed, setMiniMapCollapsed] = useState(false);
  const {
    viewBox,
    zoomMap,
    resetView,
    focusOnSvgPoint,
    handlePointerDown,
    handlePointerMove,
    handlePointerEnd,
    handleWheel,
  } = useTownMapViewport();

  const { showNightSkip, nightSkipDay } = useNightSkipBanner(world.world_clock);
  const speechBubbles = useSpeechBubbles(world.recent_events);

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

          {nodes.map((node) => (
            <TownLocationNode
              key={node.id}
              node={node}
              agentNameMap={agentNameMap}
              highlightedLocationId={highlightedLocationId}
              heatConfig={heatConfig}
              speechBubbles={speechBubbles}
              timeStyle={timeStyle}
              viewBox={viewBox}
              onAgentClick={onAgentClick}
              onLocationClick={onLocationClick}
              setMapSummary={setMapSummary}
            />
          ))}
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
