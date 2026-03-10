"use client";

import { useMemo, useState } from "react";
import Image from "next/image";
import { createAvatar } from "@dicebear/core";
import { notionists } from "@dicebear/collection";
import { motion } from "framer-motion";

import type { AgentStatus } from "@/lib/agent-utils";

// Re-export for convenience
export type { AgentStatus } from "@/lib/agent-utils";

// 支持自定义 logo 的 agent 配置 ID 列表
// 已废弃：现在所有有 configId 的 agent 都默认尝试加载 /agents/{configId}.svg，加载失败自动降级

interface AgentAvatarProps {
  agentId: string;
  name: string;
  occupation?: string;
  status?: AgentStatus;
  size?: "sm" | "md" | "lg";
  showStatusRing?: boolean;
  configId?: string; // agent 配置 ID，用于加载自定义 logo
}

const sizeMap = {
  sm: { container: 32, svg: 28 },
  md: { container: 48, svg: 42 },
  lg: { container: 64, svg: 56 },
};

const statusConfig: Record<AgentStatus, { color: string; pulse: boolean; label: string }> = {
  idle: { color: "#94a3b8", pulse: false, label: "空闲" },
  working: { color: "#f59e0b", pulse: true, label: "工作中" },
  talking: { color: "#ec4899", pulse: true, label: "交谈中" },
  moving: { color: "#10b981", pulse: true, label: "移动中" },
  resting: { color: "#6366f1", pulse: false, label: "休息中" },
};

export function AgentAvatar({
  agentId,
  name,
  occupation,
  status = "idle",
  size = "md",
  showStatusRing = true,
  configId,
}: AgentAvatarProps) {
  const dimensions = sizeMap[size];
  const [useCustomLogo, setUseCustomLogo] = useState(
    !!configId  // 只要有 configId 就先尝试加载，失败后 onError 降级
  );

  // 使用 agentId 作为种子生成确定性头像（作为后备）
  const avatarSvg = useMemo(() => {
    const avatar = createAvatar(notionists, {
      seed: agentId,
      size: dimensions.svg,
      backgroundColor: ["c0aede", "d1d4f9", "ffd5dc", "ffdfbf"],
      radius: 50,
    });
    return avatar.toString();
  }, [agentId, dimensions.svg]);

  const statusStyle = statusConfig[status];

  // 自定义 logo URL - 直接使用 public 目录下的静态文件
  const customLogoUrl = configId ? `/agents/${configId}.svg` : null;

  return (
    <motion.div
      className="relative inline-flex items-center justify-center"
      style={{ width: dimensions.container, height: dimensions.container }}
      whileHover={{ scale: 1.05 }}
      transition={{ type: "spring", stiffness: 400, damping: 17 }}
    >
      {/* 状态脉冲环 */}
      {showStatusRing && statusStyle.pulse && (
        <motion.span
          className="absolute inset-0 rounded-full"
          style={{ backgroundColor: statusStyle.color }}
          animate={{
            scale: [1, 1.2, 1],
            opacity: [0.5, 0, 0.5],
          }}
          transition={{
            duration: 2,
            repeat: Infinity,
            ease: "easeInOut",
          }}
        />
      )}

      {/* 状态边框 */}
      {showStatusRing && (
        <span
          className="absolute inset-0 rounded-full border-2"
          style={{ borderColor: statusStyle.color }}
        />
      )}

      {/* 头像 */}
      <div
        className="relative overflow-hidden rounded-full bg-white shadow-xs"
        style={{
          width: dimensions.container - 4,
          height: dimensions.container - 4,
        }}
      >
        {useCustomLogo && customLogoUrl ? (
          <Image
            src={customLogoUrl}
            alt={name}
            width={dimensions.container - 4}
            height={dimensions.container - 4}
            className="object-cover"
            onError={() => setUseCustomLogo(false)}
            priority
          />
        ) : (
          <div
            dangerouslySetInnerHTML={{ __html: avatarSvg }}
            className="w-full h-full"
          />
        )}
      </div>

      {/* 职业小图标 */}
      {occupation && (
        <span
          className="absolute -bottom-0.5 -right-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-white text-[10px] shadow-xs"
          title={occupation}
        >
          {getOccupationEmoji(occupation)}
        </span>
      )}
    </motion.div>
  );
}

function getOccupationEmoji(occupation: string): string {
  const map: Record<string, string> = {
    barista: "☕",
    "hospital staff": "🏥",
    "insurance clerk": "📋",
    "office coworker": "💼",
    "shop regular": "📖",
    shopkeeper: "🏪",
    resident: "🏠",
    teacher: "📚",
    artist: "🎨",
    chef: "👨‍🍳",
    farmer: "🌾",
    doctor: "👨‍⚕️",
  };
  return map[occupation.toLowerCase()] || "👤";
}
