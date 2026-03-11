import type { ReactNode } from "react";
import { WorldProvider } from "@/components/world-context";
import { SleepAnimationWrapper } from "@/components/sleep-animation-wrapper";
import { getWorldResult } from "@/lib/api";

export const dynamic = "force-dynamic";

type RunLayoutProps = {
  children: ReactNode;
  params: Promise<{ runId: string }>;
};

export default async function RunLayout({ children, params }: RunLayoutProps) {
  const { runId } = await params;
  const initialWorld = await getWorldResult(runId);
  const initialData = initialWorld.data ?? null;

  return (
    <WorldProvider runId={runId} initialData={initialData}>
      <SleepAnimationWrapper>{children}</SleepAnimationWrapper>
    </WorldProvider>
  );
}
