import { render, type RenderResult } from "@testing-library/react";
import type { ReactElement } from "react";
import { SWRConfig } from "swr";

import { DemoAccessProvider } from "@/components/demo-access-provider";
import { RunsProvider } from "@/components/runs-provider";
import { WorldProvider } from "@/components/world-context";
import type { ApiResult } from "@/lib/api";
import type { RunSummary, WorldSnapshot } from "@/lib/types";

export function okResult<T>(data: T, status = 200): ApiResult<T> {
  return {
    data,
    error: null,
    errorCode: null,
    errorDetail: null,
    status,
  };
}

export function errorResult<T>(error: string, status: number | null = null): ApiResult<T> {
  return {
    data: null,
    error,
    errorCode: null,
    errorDetail: null,
    status,
  };
}

export function renderWithSWR(children: ReactElement): RenderResult {
  return render(
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
      {children}
    </SWRConfig>,
  );
}

export function renderHomePage(initialResult: ApiResult<RunSummary[]>): RenderResult {
  const HomePage = jest.requireActual("@/app/page").default;

  return renderWithSWR(
    <DemoAccessProvider>
      <RunsProvider initialResult={initialResult}>
        <HomePage />
      </RunsProvider>
    </DemoAccessProvider>,
  );
}

export function renderWorldPage({
  initialWorld,
  runId = "run-1",
  path = `/runs/${runId}/world`,
}: {
  initialWorld: WorldSnapshot | null;
  runId?: string;
  path?: string;
}): RenderResult {
  const WorldPage = jest.requireActual("@/app/runs/[runId]/world/page").default;

  window.history.replaceState(null, "", path);

  return renderWithSWR(
    <DemoAccessProvider>
      <WorldProvider runId={runId} initialData={initialWorld}>
        <WorldPage />
      </WorldProvider>
    </DemoAccessProvider>,
  );
}
