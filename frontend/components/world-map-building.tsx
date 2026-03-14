"use client";

import { motion } from "framer-motion";

import type { BuildingFootprint } from "@/lib/world-map-layout";
import { getPixelPalette } from "@/lib/world-map-pixel-theme";

export { getPixelPalette as getLocationBuildingStyle };

type Props = {
  centerX: number;
  centerY: number;
  footprint: BuildingFootprint;
  locationType: string;
  name: string;
  occupancyLabel: string;
  isHighlighted: boolean;
  hasHeat: boolean;
  heatScale: number;
  isDark: boolean;
};

/**
 * 等距建筑 —— 标准等距坐标系
 *
 * 底面菱形中心 = (cx, cy)
 * 顶点（底面）：
 *   前 = (cx, cy + hd)   ← 画面最前方
 *   右 = (cx + hw, cy)
 *   后 = (cx, cy - hd)
 *   左 = (cx - hw, cy)
 *
 * 顶面（上移 bh）：
 *   前顶 = (cx, cy + hd - bh)
 *   右顶 = (cx + hw, cy - bh)
 *   后顶 = (cx, cy - hd - bh)
 *   左顶 = (cx - hw, cy - bh)
 *
 * 可见三面（等距正面视角，从右上往左下看）：
 *   顶面（屋顶）：左顶 → 后顶 → 右顶 → 前顶
 *   左面：左顶 → 前顶 → 前(底) → 左(底)
 *   右面：右顶 → 前顶 → 前(底) → 右(底)
 */
export function WorldMapBuilding({
  centerX,
  centerY,
  footprint,
  locationType,
  name,
  occupancyLabel,
  isHighlighted,
  hasHeat,
  heatScale,
  isDark,
}: Props) {
  const palette = getPixelPalette(locationType);

  const hw = footprint.width / 2;
  const hd = footprint.depth / 2;
  const bh = footprint.height;

  const cx = centerX;
  const cy = centerY;

  // 底面顶点
  const bFront = { x: cx,      y: cy + hd };
  const bRight = { x: cx + hw, y: cy };
  const bLeft  = { x: cx - hw, y: cy };
  // bBack 不可见，不需要

  // 顶面顶点
  const tFront = { x: cx,      y: cy + hd - bh };
  const tRight = { x: cx + hw, y: cy - bh };
  const tBack  = { x: cx,      y: cy - hd - bh };
  const tLeft  = { x: cx - hw, y: cy - bh };

  // 三个面的多边形字符串
  const roofPts  = `${tLeft.x},${tLeft.y} ${tBack.x},${tBack.y} ${tRight.x},${tRight.y} ${tFront.x},${tFront.y}`;
  const leftPts  = `${tLeft.x},${tLeft.y} ${tFront.x},${tFront.y} ${bFront.x},${bFront.y} ${bLeft.x},${bLeft.y}`;
  const rightPts = `${tRight.x},${tRight.y} ${tFront.x},${tFront.y} ${bFront.x},${bFront.y} ${bRight.x},${bRight.y}`;

  // 热力描边颜色（用于建筑轮廓加色，不用外框）
  const heatStroke = hasHeat
    ? heatScale > 0.65 ? "#ef4444"
    : heatScale > 0.35 ? "#f59e0b"
    : "#22c55e"
    : undefined;

  const outlineW = isHighlighted ? 2 : 1;
  const outlineColor = heatStroke ?? palette.outline;

  // ── 窗格（等距立面内的正确坐标插值）──
  // 左面内部点：(u,v) → x = tLeft.x + u*(tFront.x-tLeft.x), y = tLeft.y + u*(tFront.y-tLeft.y) + v*(bLeft.y-tLeft.y)
  //   简化：tLeft.x = bLeft.x = cx-hw，所以 x 沿左边固定，沿前斜面 u 变化
  //   左面 u=横向(左→前), v=纵向(顶→底)
  //   x(u) = tLeft.x + u*(tFront.x - tLeft.x) = cx-hw + u*hw
  //   y(u,v) = tLeft.y + u*(tFront.y - tLeft.y) + v*bh = cy-bh + u*hd + v*bh

  const winRows = bh > 34 ? 2 : 1;

  // 左面窗格（沿立面 u≈0.45, v=0.25/0.6）
  const leftWins = Array.from({ length: winRows }, (_, row) => {
    const u = 0.45;
    const v = 0.22 + row * 0.38;
    return {
      x: cx - hw + u * hw,
      y: cy - bh + u * hd + v * bh,
    };
  });

  // 右面窗格（沿立面 u≈0.45, v=0.25/0.6）
  // 右面：x(u) = tRight.x - u*hw = cx+hw - u*hw, y(u,v) = cy-bh + u*hd + v*bh
  const rightWins = Array.from({ length: winRows }, (_, row) => {
    const u = 0.45;
    const v = 0.22 + row * 0.38;
    return {
      x: cx + hw - u * hw,
      y: cy - bh + u * hd + v * bh,
    };
  });

  // 窗格尺寸：在等距面内是小菱形，但用细长矩形近似（宽对应面内横向，高对应纵向）
  const winWL = Math.max(hw * 0.22, 5);  // 左面窗宽（沿面方向）
  const winWR = Math.max(hw * 0.22, 5);
  const winH  = Math.max(bh * 0.15, 4);
  const winAlpha = isDark ? 0.9 : 0.85;

  // 屋顶高光线（从左顶到前顶，提亮前侧脊线）
  const roofRidgeX1 = tLeft.x + (tFront.x - tLeft.x) * 0.08;
  const roofRidgeY1 = tLeft.y + (tFront.y - tLeft.y) * 0.08;
  const roofRidgeX2 = tLeft.x + (tFront.x - tLeft.x) * 0.88;
  const roofRidgeY2 = tLeft.y + (tFront.y - tLeft.y) * 0.88;

  // 楼层分割线（左面和右面中部水平线，让建筑有楼层感）
  const floorV = 0.48; // 立面纵向比例
  // 左面楼层线
  const lFloorL = { x: tLeft.x,  y: tLeft.y  + floorV * bh };
  const lFloorR = { x: tFront.x, y: tFront.y + floorV * bh };
  // 右面楼层线
  const rFloorL = { x: tFront.x, y: tFront.y + floorV * bh };
  const rFloorR = { x: tRight.x, y: tRight.y  + floorV * bh };

  return (
    <>
      {/* ── 右立面（最暗） ── */}
      <polygon
        points={rightPts}
        fill={palette.right}
        stroke={outlineColor}
        strokeWidth={outlineW}
        strokeLinejoin="round"
      />

      {/* ── 左立面（稍亮） ── */}
      <polygon
        points={leftPts}
        fill={palette.left}
        stroke={outlineColor}
        strokeWidth={outlineW}
        strokeLinejoin="round"
      />

      {/* ── 楼层分割线（立面内部线，制造楼层感） ── */}
      {bh > 28 && (
        <>
          <line
            x1={lFloorL.x} y1={lFloorL.y}
            x2={lFloorR.x} y2={lFloorR.y}
            stroke={palette.outline}
            strokeWidth={0.7}
            opacity={0.45}
          />
          <line
            x1={rFloorL.x} y1={rFloorL.y}
            x2={rFloorR.x} y2={rFloorR.y}
            stroke={palette.outline}
            strokeWidth={0.7}
            opacity={0.45}
          />
        </>
      )}

      {/* ── 窗格（左面） ── */}
      {leftWins.map((w, i) => (
        <rect
          key={`lw${i}`}
          x={w.x - winWL / 2}
          y={w.y - winH / 2}
          width={winWL}
          height={winH}
          fill={palette.window}
          opacity={winAlpha}
          stroke={palette.outline}
          strokeWidth={0.6}
        />
      ))}

      {/* ── 窗格（右面） ── */}
      {rightWins.map((w, i) => (
        <rect
          key={`rw${i}`}
          x={w.x - winWR / 2}
          y={w.y - winH / 2}
          width={winWR}
          height={winH}
          fill={palette.window}
          opacity={winAlpha}
          stroke={palette.outline}
          strokeWidth={0.6}
        />
      ))}

      {/* ── 屋顶 ── */}
      <polygon
        points={roofPts}
        fill={palette.roof}
        stroke={outlineColor}
        strokeWidth={isHighlighted ? 2 : 1.2}
        strokeLinejoin="round"
      />

      {/* 屋顶高光线（左侧脊线，提亮） */}
      <line
        x1={roofRidgeX1} y1={roofRidgeY1}
        x2={roofRidgeX2} y2={roofRidgeY2}
        stroke="rgba(255,255,255,0.4)"
        strokeWidth={1.5}
        strokeLinecap="round"
      />

      {/* ── 建筑图标（屋顶中心） ── */}
      <text
        x={cx}
        y={(tBack.y + tFront.y) / 2 + 1}
        textAnchor="middle"
        dominantBaseline="middle"
        fontSize={hw > 32 ? 14 : 11}
        style={{ userSelect: "none" }}
      >
        {palette.icon}
      </text>

      {/* ── 活跃状态：屋顶顶角小灯（脉冲） ── */}
      {hasHeat && (
        <motion.circle
          cx={tBack.x}
          cy={tBack.y}
          r={3}
          fill={palette.activeLamp}
          stroke={palette.outline}
          strokeWidth={0.8}
          initial={{ opacity: 0.5 }}
          animate={{ opacity: [0.4, 1, 0.4], r: [2.5, 3.5, 2.5] }}
          transition={{ duration: 1.4 + (1 - heatScale) * 1.2, repeat: Infinity, ease: "easeInOut" }}
        />
      )}

      {/* ── 高亮：屋顶描边加粗脉冲 ── */}
      {isHighlighted && (
        <motion.polygon
          points={roofPts}
          fill="none"
          stroke={outlineColor}
          strokeWidth={3}
          animate={{ opacity: [0.4, 0.9, 0.4] }}
          transition={{ duration: 1.8, repeat: Infinity }}
        />
      )}

      {/* ── 地点名称 ── */}
      <text
        x={cx}
        y={bFront.y + 13}
        textAnchor="middle"
        fontSize="11"
        fontWeight="700"
        fontFamily="monospace"
        fill={isDark ? "#e2e8f0" : "#1e293b"}
        stroke={isDark ? "rgba(15,23,42,0.75)" : "rgba(255,255,255,0.85)"}
        strokeWidth={2.5}
        paintOrder="stroke"
        style={{ userSelect: "none" }}
      >
        {name}
      </text>

      {/* ── 占用标签 ── */}
      <text
        x={cx}
        y={bFront.y + 26}
        textAnchor="middle"
        fontSize="9"
        fontWeight="500"
        fontFamily="monospace"
        fill={isDark ? "#94a3b8" : "#64748b"}
        stroke={isDark ? "rgba(15,23,42,0.7)" : "rgba(255,255,255,0.8)"}
        strokeWidth={2}
        paintOrder="stroke"
        style={{ userSelect: "none" }}
      >
        {occupancyLabel}
      </text>
    </>
  );
}
