import "./globals.css";
import type { Metadata } from "next";
import { ReactNode } from "react";
import { AppShell } from "@/components/app-shell";

export const metadata: Metadata = {
  title: "Truman World",
  description: "观察、记录、注入事件——AI 居民们不知道自己是 AI | 楚门的世界 AI 版",
  icons: {
    icon: "/icon.svg",
  },
};

export default function RootLayout({ children }: { children: ReactNode }) {
  const runtimeConfig = {
    apiBaseUrl: process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "",
  };

  return (
    <html lang="zh-CN">
      <body className="h-screen overflow-hidden">
        <script
          dangerouslySetInnerHTML={{
            __html: `window.__TRUMANWORLD_CONFIG__ = ${JSON.stringify(runtimeConfig)};`,
          }}
        />
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
