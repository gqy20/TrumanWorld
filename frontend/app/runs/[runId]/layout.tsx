import type { ReactNode } from "react";
import { WorldProvider } from "@/components/world-context";
import { SleepAnimationWrapper } from "@/components/sleep-animation-wrapper";

export const dynamic = "force-dynamic";

type RunLayoutProps = {
  children: ReactNode;
  params: Promise<{ runId: string }>;
};

export default async function RunLayout({ children, params }: RunLayoutProps) {
  const { runId } = await params;

  return (
    <WorldProvider runId={runId}>
      <SleepAnimationWrapper>{children}</SleepAnimationWrapper>
    </WorldProvider>
  );
}
