"use client";

import { useRef, type MouseEvent, type PointerEvent } from "react";

import {
  LOCATION_STYLES,
  SVG_H,
  SVG_W,
  type LocationLink,
  type PositionedLocationNode,
  type ViewBox,
} from "./town-map-utils";

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

export function MiniMap({ nodes, links, viewBox, isDark, onNavigate }: MiniMapProps) {
  const mmDragRef = useRef<{
    startX: number;
    startY: number;
    startVbX: number;
    startVbY: number;
  } | null>(null);

  const toMM = (svgX: number, svgY: number) => ({
    x: MM_PAD + (svgX / SVG_W) * (MM_W - MM_PAD * 2),
    y: MM_PAD + (svgY / SVG_H) * (MM_H - MM_PAD * 2),
  });

  const toSVG = (mmX: number, mmY: number) => ({
    x: ((mmX - MM_PAD) / (MM_W - MM_PAD * 2)) * SVG_W,
    y: ((mmY - MM_PAD) / (MM_H - MM_PAD * 2)) * SVG_H,
  });

  const frameX = MM_PAD + (viewBox.x / SVG_W) * (MM_W - MM_PAD * 2);
  const frameY = MM_PAD + (viewBox.y / SVG_H) * (MM_H - MM_PAD * 2);
  const frameW = (viewBox.width / SVG_W) * (MM_W - MM_PAD * 2);
  const frameH = (viewBox.height / SVG_H) * (MM_H - MM_PAD * 2);

  const borderColor = isDark ? "rgba(100,116,139,0.6)" : "rgba(148,163,184,0.5)";
  const gridColor = isDark ? "rgba(100,116,139,0.15)" : "rgba(148,163,184,0.18)";
  const linkColor = isDark ? "rgba(100,116,139,0.4)" : "rgba(148,163,184,0.5)";

  const handleClick = (event: MouseEvent<SVGSVGElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    const mmX = ((event.clientX - rect.left) / rect.width) * MM_W;
    const mmY = ((event.clientY - rect.top) / rect.height) * MM_H;
    const { x, y } = toSVG(mmX, mmY);
    onNavigate(x, y);
  };

  const handleFramePointerDown = (event: PointerEvent<SVGRectElement>) => {
    event.stopPropagation();
    mmDragRef.current = {
      startX: event.clientX,
      startY: event.clientY,
      startVbX: viewBox.x,
      startVbY: viewBox.y,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const handleFramePointerMove = (event: PointerEvent<SVGRectElement>) => {
    if (!mmDragRef.current) {
      return;
    }
    event.stopPropagation();
    const rect = (event.currentTarget.closest("svg") as SVGSVGElement)?.getBoundingClientRect();
    if (!rect) {
      return;
    }
    const dxPx = event.clientX - mmDragRef.current.startX;
    const dyPx = event.clientY - mmDragRef.current.startY;
    const dxSvg = (dxPx / rect.width) * MM_W * (SVG_W / (MM_W - MM_PAD * 2));
    const dySvg = (dyPx / rect.height) * MM_H * (SVG_H / (MM_H - MM_PAD * 2));
    onNavigate(
      mmDragRef.current.startVbX + dxSvg + viewBox.width / 2,
      mmDragRef.current.startVbY + dySvg + viewBox.height / 2,
    );
  };

  const handleFramePointerUp = (event: PointerEvent<SVGRectElement>) => {
    mmDragRef.current = null;
    event.currentTarget.releasePointerCapture(event.pointerId);
  };

  return (
    <svg
      width={MM_W}
      height={MM_H}
      viewBox={`0 0 ${MM_W} ${MM_H}`}
      onClick={handleClick}
      className="cursor-crosshair"
      style={{
        filter: isDark
          ? "drop-shadow(0 2px 8px rgba(0,0,0,0.4))"
          : "drop-shadow(0 2px 8px rgba(0,0,0,0.15))",
      }}
    >
      <defs>
        <radialGradient id="mm-bg-gradient" cx="50%" cy="50%" r="70%">
          <stop offset="0%" stopColor={isDark ? "rgba(30,41,59,0.7)" : "rgba(241,245,249,0.7)"} />
          <stop offset="100%" stopColor={isDark ? "rgba(15,23,42,0.95)" : "rgba(255,255,255,0.95)"} />
        </radialGradient>
        <pattern id="mm-grid" width="16" height="16" patternUnits="userSpaceOnUse">
          <path d="M 16 0 L 0 0 0 16" fill="none" stroke={gridColor} strokeWidth="0.5" />
        </pattern>
        <filter id="mm-frame-glow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="1.5" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      <rect
        x={0}
        y={0}
        width={MM_W}
        height={MM_H}
        fill="url(#mm-bg-gradient)"
        stroke={borderColor}
        strokeWidth={1}
        rx={8}
      />
      <rect x={0} y={0} width={MM_W} height={MM_H} fill="url(#mm-grid)" rx={8} />

      {links.map((link) => {
        const source = nodes.find((node) => node.id === link.source);
        const target = nodes.find((node) => node.id === link.target);
        if (!source || !target) {
          return null;
        }
        const sourcePoint = toMM(source.svgX, source.svgY);
        const targetPoint = toMM(target.svgX, target.svgY);
        return (
          <line
            key={`mm-${link.source}-${link.target}`}
            x1={sourcePoint.x}
            y1={sourcePoint.y}
            x2={targetPoint.x}
            y2={targetPoint.y}
            stroke={linkColor}
            strokeWidth={1}
          />
        );
      })}

      {nodes.map((node) => {
        const { x, y } = toMM(node.svgX, node.svgY);
        const style = LOCATION_STYLES[node.type] ?? LOCATION_STYLES.default;
        const hasOccupants = node.occupantCount > 0;
        const isActive = node.heat && node.heat > 0.5;

        return (
          <g key={`mm-node-${node.id}`}>
            {isActive && <circle cx={x} cy={y} r={9} fill={style.color} opacity={0.08} />}
            {hasOccupants && <circle cx={x} cy={y} r={7} fill={style.color} opacity={0.2} />}
            <circle
              cx={x}
              cy={y}
              r={hasOccupants ? 4.5 : 3}
              fill={hasOccupants ? style.color : isDark ? "#475569" : "#94a3b8"}
              stroke={isDark ? "rgba(15,23,42,0.8)" : "rgba(255,255,255,0.9)"}
              strokeWidth={1.5}
            />
            {node.occupantCount > 0 && (
              <g>
                <circle
                  cx={x + 6}
                  cy={y - 3}
                  r={4}
                  fill={isDark ? "#1e293b" : "#ffffff"}
                  stroke={isDark ? "#475569" : "#e2e8f0"}
                  strokeWidth={1}
                />
                <text
                  x={x + 6}
                  y={y - 1.5}
                  fontSize={4.5}
                  fontWeight="700"
                  fill={isDark ? "#94a3b8" : "#64748b"}
                  textAnchor="middle"
                >
                  {node.occupantCount}
                </text>
              </g>
            )}
          </g>
        );
      })}

      <rect
        x={frameX}
        y={frameY}
        width={Math.max(frameW, 4)}
        height={Math.max(frameH, 4)}
        fill="rgba(59,130,246,0.12)"
        stroke="rgba(59,130,246,0.85)"
        strokeWidth={1.5}
        rx={3}
        filter="url(#mm-frame-glow)"
        className="cursor-move"
        onPointerDown={handleFramePointerDown}
        onPointerMove={handleFramePointerMove}
        onPointerUp={handleFramePointerUp}
        onPointerCancel={handleFramePointerUp}
        onClick={(event) => event.stopPropagation()}
      />
    </svg>
  );
}
