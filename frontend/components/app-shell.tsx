"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { type ReactNode, useState } from "react";
import useSWR from "swr";
import { buildApiUrl, fetchApiOrFallback } from "@/lib/api";
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
  const [isCollapsed, setIsCollapsed] = useState(false);
  const { data: runs } = useSWR<RunSummary[]>(
    buildApiUrl("/runs"),
    (url: string) => fetchApiOrFallback<RunSummary[]>(url, []),
    {
      refreshInterval: 10000,
    },
  );

  return (
    <div className="flex h-screen w-screen overflow-hidden">
      <nav
        className={`flex flex-shrink-0 flex-col border-r border-white/60 bg-[linear-gradient(180deg,rgba(255,255,255,0.88),rgba(247,249,252,0.72))] backdrop-blur-xl transition-all duration-300 ${
          isCollapsed ? "w-16" : "w-[272px]"
        }`}
      >
        <div className="flex items-center justify-between border-b border-white/60 px-4 py-3">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center overflow-hidden rounded-xl shadow-md shadow-slate-900/10">
              <Image src="/logo.svg" alt="Truman World Logo" width={36} height={36} priority />
            </div>
            {!isCollapsed && (
              <div className="overflow-hidden">
                <h1 className="text-sm font-semibold text-ink">Truman World</h1>
                <p className="text-xs text-slate-400">导演控制台</p>
              </div>
            )}
          </div>

          <button
            type="button"
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="flex h-7 w-7 items-center justify-center rounded-lg text-slate-400 transition hover:bg-slate-100 hover:text-slate-600"
            title={isCollapsed ? "展开" : "收起"}
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              className={`h-4 w-4 transition-transform duration-300 ${isCollapsed ? "rotate-180" : ""}`}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
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
                isCollapsed={isCollapsed}
              />
            ))}
          </div>

          {!isCollapsed && runs && runs.length > 0 && (
            <div className="mt-4 px-3">
              <p className="mb-2 px-2 text-xs font-medium uppercase tracking-[0.2em] text-slate-400">
                世界列表
              </p>
              <div className="space-y-0.5">
                {runs.map((run) => (
                  <RunListItem key={run.id} run={run} />
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="border-t border-white/60 p-3">
          {!isCollapsed ? (
            <div className="flex items-center justify-between rounded-xl bg-white/50 px-3 py-2">
              <span className="text-xs text-slate-400">v0.1.0</span>
              <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-500">MVP</span>
            </div>
          ) : (
            <div className="flex justify-center">
              <span className="text-xs text-slate-400">v0.1</span>
            </div>
          )}
        </div>
      </nav>

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

function RunListItem({ run }: { run: RunSummary }) {
  const pathname = usePathname();
  const isActive = pathname.startsWith(`/runs/${run.id}`);

  return (
    <Link
      href={`/runs/${run.id}/world`}
      className={`group flex items-center gap-2 rounded-lg px-2 py-1.5 transition ${
        isActive
          ? "bg-white text-moss shadow-sm"
          : "text-slate-600 hover:bg-white/60 hover:text-ink"
      }`}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full ${
          run.status === "running" ? "bg-emerald-500" : "bg-amber-500"
        }`}
      />
      <div className="min-w-0 flex-1">
        <p className={`truncate text-sm ${isActive ? "font-medium" : ""}`}>{run.name}</p>
        <p className="text-xs text-slate-400">
          Tick {run.current_tick ?? 0}
        </p>
      </div>
      {isActive && (
        <svg className="h-3.5 w-3.5 text-moss/60" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M9 5l7 7-7 7" />
        </svg>
      )}
    </Link>
  );
}
