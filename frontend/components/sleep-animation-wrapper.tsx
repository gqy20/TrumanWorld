"use client";

import type { ReactNode } from "react";
import { SleepTransitionAnimation } from "@/components/sleep-transition-animation";

type Props = {
  children: ReactNode;
};

/**
 * 客户端包装组件，提供全局效果（如睡眠过渡动画）
 */
export function SleepAnimationWrapper({ children }: Props) {
  return (
    <>
      {children}
      <SleepTransitionAnimation />
    </>
  );
}
