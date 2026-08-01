import "./globals.css";
import type { Metadata } from "next";
import { ReactNode } from "react";
import { AppShell } from "@/components/app-shell";
import { DemoAccessProvider } from "@/components/demo-access-provider";
import { RunsProvider } from "@/components/runs-provider";
import { fetchApiResult, getInternalApiBaseUrl, type ApiResult } from "@/lib/api";
import type { RunSummary } from "@/lib/types";

export const metadata: Metadata = {
  title: "楚门世界",
  description: "观察、记录、注入事件，管理一个可持续运行的 AI 社会模拟世界",
  icons: {
    icon: "/icon.svg",
  },
};

export default async function RootLayout({ children }: { children: ReactNode }) {
  const railwayBackendApiBaseUrl = process.env.RAILWAY_SERVICE_BACKEND_URL
    ? `https://${process.env.RAILWAY_SERVICE_BACKEND_URL.replace(/\/$/, "")}/api`
    : undefined;
  const runtimeConfig = {
    apiBaseUrl:
      railwayBackendApiBaseUrl ??
      process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ??
      "/api",
  };
  const initialRunsResult: ApiResult<RunSummary[]> = await fetchApiResult<RunSummary[]>(
    `${getInternalApiBaseUrl()}/runs`,
  );

  return (
    <html lang="zh-CN">
      <body className="min-h-screen overflow-x-hidden lg:h-screen lg:overflow-hidden">
        <script
          dangerouslySetInnerHTML={{
            __html: `window.__TRUMANWORLD_CONFIG__ = ${JSON.stringify(runtimeConfig)};`,
          }}
        />
        <DemoAccessProvider>
          <RunsProvider initialResult={initialRunsResult}>
            <AppShell>{children}</AppShell>
          </RunsProvider>
        </DemoAccessProvider>
      </body>
    </html>
  );
}
