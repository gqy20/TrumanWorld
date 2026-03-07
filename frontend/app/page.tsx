import Link from "next/link";

import { NavLink } from "@/components/nav-link";
import { CreateRunForm } from "@/components/create-run-form";
import { RunList } from "@/components/run-list";
import { SectionCard } from "@/components/section-card";
import { listRuns } from "@/lib/api";

export default async function HomePage() {
  const runs = await listRuns();

  return (
    <main className="min-h-screen px-6 py-12">
      <div className="mx-auto max-w-5xl space-y-8">
        <header className="space-y-4">
          <p className="text-sm uppercase tracking-[0.3em] text-moss">Director Console</p>
          <h1 className="text-5xl font-semibold">AI Truman World</h1>
          <p className="max-w-2xl text-lg text-slate-700">
            导演控制台已经接入真实 API 页面结构。你可以从这里进入 run、timeline 和 agent
            检视流程。
          </p>
        </header>
        <section className="grid gap-4 md:grid-cols-4">
          <NavLink href="/runs/00000000-0000-0000-0000-000000000001" eyebrow="Runs" title="Run Detail">
            查看单个运行的状态、tick 和控制入口。
          </NavLink>
          <NavLink
            href="/runs/00000000-0000-0000-0000-000000000001/world"
            eyebrow="Viewer"
            title="World Viewer"
          >
            面向观众的小镇观看页，显示地点与人物分布。
          </NavLink>
          <NavLink
            href="/runs/00000000-0000-0000-0000-000000000001/timeline"
            eyebrow="Timeline"
            title="Timeline"
          >
            追踪事件流与导演注入事件。
          </NavLink>
          <NavLink
            href="/runs/00000000-0000-0000-0000-000000000001/agents/demo_agent"
            eyebrow="Agents"
            title="Agent Inspector"
          >
            检查单个 agent 的状态、记忆和关系。
          </NavLink>
        </section>

        <SectionCard title="Create Run" description="最小导演控制动作：创建新的模拟运行。">
          <CreateRunForm />
        </SectionCard>

        <SectionCard title="Recent Runs" description="从后端读取最近的模拟运行，直接进入导演视图。悬停可删除。">
          <RunList runs={runs} />
        </SectionCard>
      </div>
    </main>
  );
}
