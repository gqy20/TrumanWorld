"use client";

import { motion, useReducedMotion } from "framer-motion";

export function WorldOpeningAnimation({ runName }: { runName?: string }) {
  const prefersReducedMotion = useReducedMotion();

  return (
    <div
      role="status"
      aria-live="polite"
      aria-busy="true"
      className="fixed inset-0 z-[9999] flex items-center justify-center bg-[#172338] px-6 text-center text-white"
    >
      <motion.div
        initial={prefersReducedMotion ? false : { opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: prefersReducedMotion ? 0 : 0.22, ease: [0.22, 1, 0.36, 1] }}
        className="flex max-w-sm flex-col items-center"
      >
        <TownLoadingMark reducedMotion={Boolean(prefersReducedMotion)} />
        <p className="mt-6 text-lg font-semibold tracking-tight text-white">
          {runName ? `正在进入 ${runName}` : "正在准备小镇"}
        </p>
        <p className="mt-2 text-sm text-[#cbd8ca]">同步道路、居民与最近事件</p>
        <span className="sr-only">世界数据加载中</span>
      </motion.div>
    </div>
  );
}

function TownLoadingMark({ reducedMotion }: { reducedMotion: boolean }) {
  return (
    <motion.svg
      aria-hidden="true"
      viewBox="0 0 144 104"
      className="h-[6.5rem] w-36"
      animate={reducedMotion ? undefined : { y: [0, -2, 0] }}
      transition={{ duration: 2.2, ease: "easeInOut", repeat: Infinity }}
    >
      <path d="M12 67 72 35l60 32-60 33Z" fill="#667c5b" />
      <path d="m12 67 60 33 60-33v8l-60 29-60-29Z" fill="#40533e" />
      <path d="m32 68 40-21 40 21-40 21Z" fill="#a9a49a" />
      <path d="m68 48 8-4 5 3-8 4Z" fill="#d8d4cb" />
      <path d="m70 87 9-5 5 3-9 5Z" fill="#d8d4cb" />
      <g>
        <path d="m37 55 17-9 17 9-17 9Z" fill="#a45345" />
        <path d="m40 55 14 7v18l-14-7Z" fill="#e7e7e1" />
        <path d="m54 62 14-7v18l-14 7Z" fill="#cfd4cb" />
        <path d="m58 64 5-3v7l-5 3Z" fill="#f2b45b" />
      </g>
      <g>
        <path d="m78 47 14-7 14 7-14 8Z" fill="#526b7a" />
        <path d="m80 47 12 6v20l-12-6Z" fill="#e7e7e1" />
        <path d="m92 53 12-6v20l-12 6Z" fill="#cfd4cb" />
        <path d="m95 56 5-2v6l-5 3Z" fill="#f2b45b" />
      </g>
      <g>
        <path d="M107 69c0-7 4-13 9-13s9 6 9 13c0 5-4 8-9 8s-9-3-9-8Z" fill="#7f9a68" />
        <path d="M114 75h4v12h-4Z" fill="#6c4a35" />
      </g>
    </motion.svg>
  );
}
