"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { type ReactNode, useState, useEffect } from "react";
import useSWR from "swr";
import { buildApiUrl, fetchApiResult, type ApiResult } from "@/lib/api";
import type { RunSummary } from "@/lib/types";

type AppShellProps = {
  children: ReactNode;
};

const NAV_ITEMS = [
  {
    href: "/",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5">
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 9.75L12 3l9 6.75V21a.75.75 0 01-.75.75H15v-6H9v6H3.75A.75.75 0 013 21V9.75z" />
      </svg>
    ),
    label: "控制台",
    exact: true,
  },
];

export function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();
  // 在世界页面默认折叠左侧栏
  const isWorldPage = pathname.includes("/world");
  const [isCollapsed, setIsCollapsed] = useState(isWorldPage);
  
  // 当路径变化时，如果在世界页面则折叠
  useEffect(() => {
    if (pathname.includes("/world")) {
      setIsCollapsed(true);
    }
  }, [pathname]);
  
  const { data: runsResult } = useSWR<ApiResult<RunSummary[]>>(
    buildApiUrl("/runs"),
    fetchApiResult,
    {
      refreshInterval: 10000,
      fallbackData: {
        data: [],
        error: null,
        status: null,
      },
    },
  );
  const runs = runsResult?.data ?? [];

  return (
    <div className="flex h-screen w-screen overflow-hidden">
      {/* 侧边栏 - 完全折叠时隐藏 */}
      <nav
        className={`flex flex-shrink-0 flex-col border-r border-white/60 bg-[linear-gradient(180deg,rgba(255,255,255,0.88),rgba(247,249,252,0.72))] backdrop-blur-xl transition-all duration-300 ${
          isCollapsed ? "w-0 opacity-0 overflow-hidden" : "w-[272px] opacity-100"
        }`}
      >
        <div className="flex items-center justify-between border-b border-white/60 px-4 py-3">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center overflow-hidden rounded-xl shadow-md shadow-slate-900/10">
              <Image src="/logo.svg" alt="Truman World Logo" width={36} height={36} priority />
            </div>
            <div className="overflow-hidden">
              <h1 className="text-sm font-semibold text-ink">Truman World</h1>
              <p className="text-xs text-slate-400">楚门的世界 AI 版 · 导演控制台</p>
            </div>
          </div>

          <button
            type="button"
            onClick={() => setIsCollapsed(true)}
            className="flex h-7 w-7 items-center justify-center rounded-lg text-slate-400 transition-all hover:bg-slate-100 hover:text-slate-600 active:scale-95"
            title="收起侧边栏"
          >
            {/* 双竖线向左箭头，更优雅的折叠图标 */}
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-4 w-4">
              <path d="M11 6l-6 6 6 6" strokeLinecap="round" strokeLinejoin="round" />
              <path d="M16 6l-6 6 6 6" strokeLinecap="round" strokeLinejoin="round" opacity="0.5" />
            </svg>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto py-3">
          <div className="px-3">
            {NAV_ITEMS.map((item) => (
              <SidebarNavItemWide
                key={item.href}
                href={item.href}
                icon={item.icon}
                label={item.label}
                exact={item.exact}
                isCollapsed={false}
              />
            ))}
          </div>

          {runsResult?.error ? (
            <div className="mt-4 px-3">
              <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-800">
                {runsResult.error === "network_error" ? "运行列表暂时不可达" : "运行列表加载失败"}
              </div>
            </div>
          ) : null}

          {runs && runs.length > 0 && (
            <div className="mt-4 px-3">
              <div className="mb-2 flex items-center justify-between px-2">
                <p className="text-xs font-medium uppercase tracking-[0.2em] text-slate-400">
                  世界列表
                </p>
                <span className="text-[10px] text-slate-400">{runs.length} 个</span>
              </div>
              <div className="space-y-1">
                {runs.map((run, index) => (
                  <RunListItem key={run.id} run={run} index={index} />
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="border-t border-white/60 p-3">
          <div className="flex items-center justify-between rounded-xl bg-white/50 px-3 py-2">
            <span className="text-xs text-slate-400">v0.1.0</span>
            <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-500">MVP</span>
          </div>
        </div>
      </nav>

      {/* 展开按钮 - 参考 ChatGPT 风格，侧边栏折叠时显示在左边缘 */}
      {isCollapsed && (
        <button
          type="button"
          onClick={() => setIsCollapsed(false)}
          className="absolute left-0 top-1/2 z-50 flex h-12 w-6 -translate-y-1/2 items-center justify-center rounded-r-lg border border-l-0 border-slate-200 bg-white/90 text-slate-400 shadow-sm backdrop-blur transition-all hover:w-7 hover:bg-white hover:text-slate-600"
          title="展开侧边栏"
        >
          {/* 双竖线图标 - 参考 ChatGPT */}
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-4 w-4">
            <path d="M9 6v12M15 6v12" />
          </svg>
        </button>
      )}

      <div className="flex flex-1 flex-col overflow-hidden">{children}</div>
    </div>
  );
}

function SidebarNavItemWide({
  href,
  icon,
  label,
  exact = false,
  isCollapsed = false,
}: {
  href: string;
  icon: ReactNode;
  label: string;
  exact?: boolean;
  isCollapsed?: boolean;
}) {
  const pathname = usePathname();
  const isActive = exact ? pathname === href : pathname.startsWith(href);

  return (
    <Link
      href={href}
      title={label}
      className={`flex items-center transition-all ${
        isCollapsed
          ? "justify-center rounded-lg px-2 py-2"
          : "gap-2.5 rounded-xl px-2.5 py-2"
      } ${
        isActive
          ? "bg-white text-moss shadow-sm"
          : "text-slate-600 hover:bg-white/60 hover:text-ink"
      }`}
    >
      <span className={`${isActive ? "text-moss" : "text-slate-400"} ${isCollapsed ? "" : "h-5 w-5"}`}>
        {icon}
      </span>
      {!isCollapsed && <span className={`text-sm ${isActive ? "font-medium" : ""}`}>{label}</span>}
    </Link>
  );
}

function RunListItem({ run, index }: { run: RunSummary; index: number }) {
  const pathname = usePathname();
  const isActive = pathname.startsWith(`/runs/${run.id}`);

  return (
    <Link
      href={`/runs/${run.id}/world`}
      className={`group flex items-center gap-3 rounded-xl px-3 py-2.5 transition-all ${
        isActive
          ? "bg-white text-moss shadow-sm ring-1 ring-black/5"
          : "text-slate-600 hover:bg-white/60 hover:text-ink"
      }`}
    >
      {/* 序号替代小圆点，更优雅 */}
      <span className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-md text-[10px] font-medium ${
        isActive
          ? "bg-moss/10 text-moss"
          : run.status === "running"
            ? "bg-emerald-50 text-emerald-600"
            : "bg-slate-100 text-slate-500"
      }`}>
        {index + 1}
      </span>
      <div className="min-w-0 flex-1">
        <p className={`truncate text-sm ${isActive ? "font-medium" : ""}`}>{run.name}</p>
        <p className="text-xs text-slate-400">
          Tick {run.current_tick ?? 0}
          {run.status === "running" && (
            <span className="ml-1.5 inline-flex items-center gap-0.5">
              <span className="h-1 w-1 animate-pulse rounded-full bg-emerald-500" />
              运行中
            </span>
          )}
        </p>
      </div>
      {isActive && (
        <svg className="h-4 w-4 text-moss/60" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M9 5l7 7-7 7" />
        </svg>
      )}
    </Link>
  );
}
