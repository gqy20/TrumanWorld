"use client";

import { motion } from "framer-motion";
import { AgentAvatar } from "@/components/agent-avatar";
import { TypewriterText } from "@/components/typewriter-text";

interface ConversationBubbleProps {
  speakerId: string;
  speakerName: string;
  message: string;
  isAgent: boolean;
  isStreaming?: boolean;
  occupation?: string;
  configId?: string;
}

export function ConversationBubble({
  speakerId,
  speakerName,
  message,
  isAgent,
  isStreaming = false,
  occupation,
  configId,
}: ConversationBubbleProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: "spring", stiffness: 300, damping: 24 }}
      className={`flex gap-2.5 ${isAgent ? "" : "flex-row-reverse"}`}
    >
      {/* 头像 */}
      <AgentAvatar
        agentId={speakerId}
        name={speakerName}
        occupation={occupation}
        size="sm"
        configId={configId}
      />

      {/* 气泡 */}
      <div
        className={`
          max-w-[75%] rounded-2xl px-4 py-2.5
          ${
            isAgent
              ? "rounded-tl-md bg-slate-100 text-slate-900 dark:bg-slate-700 dark:text-slate-100"
              : "rounded-tr-md bg-moss text-white"
          }
        `}
      >
        {/* 说话者名称 */}
        <p
          className={`mb-1 text-[10px] font-medium uppercase tracking-wider ${
            isAgent ? "text-slate-500 dark:text-slate-400" : "text-white/70"
          }`}
        >
          {speakerName}
        </p>
        
        {/* 消息内容 */}
        <p className="text-sm leading-relaxed">
          {isStreaming ? (
            <TypewriterText text={message} speed={25} />
          ) : (
            message
          )}
        </p>
      </div>
    </motion.div>
  );
}
