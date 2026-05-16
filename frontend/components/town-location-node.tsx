"use client";

import { type KeyboardEvent } from "react";
import { motion } from "framer-motion";

import { buildHeatGlowMotionProps, buildHeatRingMotionProps } from "@/lib/world-map-motion";
import { getHeatLevel, getTimeOfDayStyle, type LocationHeatConfig } from "@/lib/world-utils";

import {
  LOCATION_STYLES,
  NODE_SCALE,
  SVG_W,
  agentColor,
  type PositionedLocationNode,
  type ViewBox,
} from "./town-map-utils";
import type { SpeechBubbleMap } from "./use-speech-bubbles";

interface TownLocationNodeProps {
  node: PositionedLocationNode;
  agentNameMap: Record<string, string>;
  highlightedLocationId?: string | null;
  heatConfig?: LocationHeatConfig;
  speechBubbles: SpeechBubbleMap;
  timeStyle: ReturnType<typeof getTimeOfDayStyle>;
  viewBox: ViewBox;
  onAgentClick?: (agentId: string) => void;
  onLocationClick?: (locationId: string) => void;
  setMapSummary: (label: string | null) => void;
}

export function TownLocationNode({
  node,
  agentNameMap,
  highlightedLocationId,
  heatConfig,
  speechBubbles,
  timeStyle,
  viewBox,
  onAgentClick,
  onLocationClick,
  setMapSummary,
}: TownLocationNodeProps) {
  const style = LOCATION_STYLES[node.type] ?? LOCATION_STYLES.default;
  const isHighlighted = node.id === highlightedLocationId;
  const outerRadius = (32 + node.capacity * 2.5) * NODE_SCALE;
  const heatLevel = getHeatLevel(node.heat, heatConfig);
  const glowThreshold = heatConfig?.glowThreshold ?? 0.1;
  const hasHeat = node.heat > glowThreshold;
  const heatGlowMotion = buildHeatGlowMotionProps(node.heat);
  const heatRingMotion = buildHeatRingMotionProps(node.heat);
  const locationSummary = `${node.name} · ${node.occupantCount}/${node.capacity} · ${heatLevel.label}`;

  return (
    <g
      data-map-interactive="true"
      role="button"
      tabIndex={0}
      aria-label={`${node.name}，当前 ${node.occupantCount} / ${node.capacity} 人，${heatLevel.label}`}
      onMouseEnter={() => setMapSummary(locationSummary)}
      onMouseLeave={() => setMapSummary(null)}
      onFocus={() => setMapSummary(locationSummary)}
      onBlur={() => setMapSummary(null)}
      onClick={() => {
        setMapSummary(locationSummary);
        onLocationClick?.(node.id);
      }}
      onKeyDown={(event: KeyboardEvent<SVGGElement>) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          setMapSummary(locationSummary);
          onLocationClick?.(node.id);
        }
      }}
      className="cursor-pointer outline-hidden focus:outline-hidden"
    >
      <title>{locationSummary}</title>
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
        const ringRadius = outerRadius + 22 * NODE_SCALE;
        const totalAgents = node.occupants.length;
        const startAngle = (-150 * Math.PI) / 180;
        const endAngle = (150 * Math.PI) / 180;
        const angle =
          totalAgents === 1
            ? -Math.PI / 2
            : startAngle + (index / (totalAgents - 1)) * (endAngle - startAngle);
        const agentX = node.svgX + Math.cos(angle) * ringRadius;
        const agentY = node.svgY + Math.sin(angle) * ringRadius;
        const fill = agentColor(agent.id);
        const label = agentNameMap[agent.id] ?? agent.name;
        const hasLogo = !!agent.config_id;
        const agentSummary = `${label} · ${agent.current_goal ?? "空闲中"}`;

        return (
          <g
            key={agent.id}
            data-map-interactive="true"
            role="button"
            tabIndex={0}
            aria-label={`${label}，当前目标 ${agent.current_goal ?? "空闲中"}`}
            onClick={(event) => {
              event.stopPropagation();
              setMapSummary(agentSummary);
              onAgentClick?.(agent.id);
            }}
            onKeyDown={(event: KeyboardEvent<SVGGElement>) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                event.stopPropagation();
                setMapSummary(agentSummary);
                onAgentClick?.(agent.id);
              }
            }}
            onMouseEnter={() => setMapSummary(agentSummary)}
            onMouseLeave={() => setMapSummary(null)}
            onFocus={() => setMapSummary(agentSummary)}
            onBlur={() => setMapSummary(null)}
            className="cursor-pointer"
          >
            <title>{agentSummary}</title>
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
            {speechBubbles[agent.id] ? (
              <AgentSpeechBubble
                agentX={agentX}
                agentY={agentY}
                bubble={speechBubbles[agent.id]}
                fill={fill}
                isDark={timeStyle.isDark}
                viewBoxY={viewBox.y}
              />
            ) : null}
          </g>
        );
      })}
    </g>
  );
}

interface AgentSpeechBubbleProps {
  agentX: number;
  agentY: number;
  bubble: {
    message: string;
    key: number;
  };
  fill: string;
  isDark: boolean;
  viewBoxY: number;
}

function AgentSpeechBubble({
  agentX,
  agentY,
  bubble,
  fill,
  isDark,
  viewBoxY,
}: AgentSpeechBubbleProps) {
  const maxChars = 28;
  const displayMsg =
    bubble.message.length > maxChars ? `${bubble.message.slice(0, maxChars)}…` : bubble.message;
  const bubbleW = 120;
  const bubbleH = 36;
  const tailH = 8;
  const margin = 6;
  const rawBubbleX = agentX - bubbleW / 2;
  const clampedBubbleX = Math.max(margin, Math.min(rawBubbleX, SVG_W - bubbleW - margin));
  const tailCX = Math.max(clampedBubbleX + 8, Math.min(agentX, clampedBubbleX + bubbleW - 8));
  const spaceAbove = agentY - viewBoxY;
  const showBelow = spaceAbove < bubbleH + tailH + 20;
  const bubbleY = showBelow
    ? agentY + 16 * NODE_SCALE + tailH + 4
    : agentY - 16 * NODE_SCALE - bubbleH - tailH - 4;
  const bgColor = isDark ? "rgba(30,41,59,0.96)" : "rgba(255,255,255,0.96)";
  const textColor = isDark ? "#e2e8f0" : "#1e293b";
  const tailPoints = showBelow
    ? `${tailCX - 5},${bubbleY} ${tailCX + 5},${bubbleY} ${tailCX},${bubbleY - tailH}`
    : `${tailCX - 5},${bubbleY + bubbleH} ${tailCX + 5},${bubbleY + bubbleH} ${tailCX},${bubbleY + bubbleH + tailH}`;

  return (
    <motion.g
      key={bubble.key}
      initial={{ opacity: 0, y: showBelow ? -4 : 4 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: showBelow ? -4 : 4 }}
      transition={{ duration: 0.3 }}
    >
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
      <polygon points={tailPoints} fill={bgColor} stroke={fill} strokeWidth={1.5} />
      <rect
        x={tailCX - 5}
        y={showBelow ? bubbleY - 2 : bubbleY + bubbleH - 2}
        width={10}
        height={4}
        fill={bgColor}
      />
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
}
