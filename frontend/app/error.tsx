"use client";

import { useEffect } from "react";
import { ErrorState } from "@/components/error-state";
import { reportApplicationError } from "@/lib/observability";

export default function RouteError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    reportApplicationError(error, {
      boundary: "route",
      digest: error.digest,
    });
  }, [error]);

  return (
    <main className="flex min-h-[60vh] items-center justify-center px-6">
      <ErrorState message="当前页面发生异常。" onRetry={reset} size="lg" />
    </main>
  );
}
