"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ReactNode } from "react";

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
  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-50">
      {/* 左侧导航栏 - 加宽并增加功能分区 */}
      <nav className="flex w-64 flex-shrink-0 flex-col border-r border-slate-200 bg-white">
        {/* Logo 区域 */}
        <div className="flex items-center gap-3 border-b border-slate-100 px-5 py-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-ink to-slate-700 text-white shadow-sm">
            <span className="text-sm font-bold">TW</span>
          </div>
          <div>
            <h1 className="text-sm font-semibold text-ink">Truman World</h1>
            <p className="text-[10px] text-slate-400">导演控制台</p>
          </div>
        </div>

        {/* 主导航 */}
        <div className="flex-1 overflow-y-auto py-4">
          <div className="px-3">
            <p className="mb-2 px-3 text-[10px] font-medium uppercase tracking-wider text-slate-400">
              主要
            </p>
            {NAV_ITEMS.map((item) => (
              <SidebarNavItemWide
                key={item.href}
                href={item.href}
                icon={item.icon}
                label={item.label}
                exact={item.exact}
              />
            ))}
          </div>


        </div>

        {/* 底部信息 */}
        <div className="border-t border-slate-100 p-4">
          <div className="rounded-xl bg-slate-50 p-3">
            <p className="text-[10px] text-slate-400">版本</p>
            <p className="text-xs font-medium text-slate-600">v0.1.0 MVP</p>
          </div>
        </div>
      </nav>

      {/* 右侧主内容区 */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {children}
      </div>
    </div>
  );
}

// 宽版导航项组件
function SidebarNavItemWide({
  href,
  icon,
  label,
  exact = false,
}: {
  href: string;
  icon: ReactNode;
  label: string;
  exact?: boolean;
}) {
  const pathname = usePathname();
  const isActive = exact ? pathname === href : pathname.startsWith(href);

  return (
    <Link
      href={href}
      className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-all ${
        isActive
          ? "bg-moss/10 text-moss font-medium"
          : "text-slate-600 hover:bg-slate-50 hover:text-ink"
      }`}
    >
      <span className={isActive ? "text-moss" : "text-slate-400"}>{icon}</span>
      {label}
    </Link>
  );
}
