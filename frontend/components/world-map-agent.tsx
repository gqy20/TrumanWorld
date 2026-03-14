"use client";

import { useState } from "react";

/**
 * 像素小人（紧凑版）
 * 高度约 22px，宽度约 12px，底座 8px
 * hover 时头顶显示气泡徽章
 */
type Props = {
  x: number;
  y: number;
  fill: string;
  label: string;
  hasLogo: boolean;
  configId?: string | null;
  isDark: boolean;
};

export function WorldMapAgent({ x, y, fill, label, hasLogo, configId, isDark }: Props) {
  const [hovered, setHovered] = useState(false);

  const outline = isDark ? "#1e293b" : "#0f172a";
  const bodyShade = isDark ? "#334155" : "#475569";
  const legColor  = isDark ? "#1e293b" : "#334155";

  // 小人各部件坐标（以 x,y 为头部中心上方）
  // 头：6×6
  const headX = x - 3;
  const headY = y;
  // 身体：8×6（分两层）
  const bodyX = x - 4;
  const bodyY = y + 6;
  // 腿：各 3×4
  const legLX = x - 4;
  const legRX = x + 1;
  const legY  = y + 14;
  // 底座菱形（小）
  const base = {
    top:   `${x},${y + 18} ${x + 6},${y + 21} ${x},${y + 24} ${x - 6},${y + 21}`,
    left:  `${x - 6},${y + 21} ${x},${y + 24} ${x},${y + 27} ${x - 6},${y + 24}`,
    right: `${x + 6},${y + 21} ${x},${y + 24} ${x},${y + 27} ${x + 6},${y + 24}`,
  };

  return (
    <g
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {/* 底座 */}
      <polygon points={base.top}   fill={isDark ? "#475569" : "#94a3b8"} stroke={outline} strokeWidth={0.7} />
      <polygon points={base.left}  fill={isDark ? "#334155" : "#64748b"} stroke={outline} strokeWidth={0.7} />
      <polygon points={base.right} fill={isDark ? "#1e293b" : "#475569"} stroke={outline} strokeWidth={0.7} />

      {/* 腿 */}
      <rect x={legLX} y={legY} width={3} height={4} fill={legColor}  stroke={outline} strokeWidth={0.6} />
      <rect x={legRX} y={legY} width={3} height={4} fill={legColor}  stroke={outline} strokeWidth={0.6} />

      {/* 身体下半（裤子色） */}
      <rect x={bodyX} y={bodyY + 3} width={8} height={3} fill={bodyShade} stroke={outline} strokeWidth={0.6} />
      {/* 身体上半（角色主色衣服） */}
      <rect x={bodyX} y={bodyY}     width={8} height={4} fill={fill}      stroke={outline} strokeWidth={0.6} />

      {/* 头 */}
      <rect x={headX} y={headY} width={6} height={6} fill={fill} stroke={outline} strokeWidth={0.8} />
      {/* 眼睛 */}
      <rect x={x - 2} y={y + 1} width={1} height={1} fill={outline} />
      <rect x={x + 1} y={y + 1} width={1} height={1} fill={outline} />

      {/* hover 气泡 */}
      {hovered && (
        <g>
          <rect
            x={x - 14}
            y={y - 19}
            width={28}
            height={16}
            rx={2}
            fill={isDark ? "#1e293b" : "#ffffff"}
            stroke={fill}
            strokeWidth={1.2}
          />
          {/* 气泡小三角 */}
          <polygon
            points={`${x - 3},${y - 3} ${x + 3},${y - 3} ${x},${y}`}
            fill={isDark ? "#1e293b" : "#ffffff"}
            stroke={fill}
            strokeWidth={0.8}
          />
          {hasLogo && configId ? (
            <image
              href={`/agents/${configId}.svg`}
              x={x - 8}
              y={y - 17}
              width="16"
              height="12"
            />
          ) : (
            <text
              x={x}
              y={y - 10}
              textAnchor="middle"
              dominantBaseline="middle"
              fontSize="8"
              fontWeight="800"
              fontFamily="monospace"
              fill={fill}
            >
              {label.slice(0, 3)}
            </text>
          )}
        </g>
      )}
    </g>
  );
}
