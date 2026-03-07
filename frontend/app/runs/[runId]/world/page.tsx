import Link from "next/link";

import { SectionCard } from "@/components/section-card";
import { WorldLiveControls } from "@/components/world-live-controls";
import { getWorld } from "@/lib/api";

type WorldPageProps = {
  params: Promise<{ runId: string }>;
};

function locationTone(locationType: string): string {
  if (locationType === "cafe") return "border-amber-200 bg-amber-50";
  if (locationType === "plaza") return "border-sky-200 bg-sky-50";
  return "border-slate-200 bg-white";
}

function agentTone(occupation?: string) {
  if (occupation === "barista") return "bg-amber-100 text-amber-900";
  if (occupation === "resident") return "bg-sky-100 text-sky-900";
  return "bg-slate-100 text-slate-900";
}

function initials(name: string) {
  return name
    .split(/\s+/)
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

function describeEvent(event: NonNullable<Awaited<ReturnType<typeof getWorld>>>["recent_events"][number]) {
  if (event.event_type === "move") {
    return `${event.actor_agent_id ?? "Someone"} walked to ${String(event.payload.to_location_id ?? event.location_id ?? "somewhere")}.`;
  }
  if (event.event_type === "talk") {
    return `${event.actor_agent_id ?? "Someone"} talked with ${event.target_agent_id ?? "someone"} at ${event.location_id ?? "town"}.`;
  }
  if (event.event_type === "work") {
    return `${event.actor_agent_id ?? "Someone"} spent this tick working.`;
  }
  if (event.event_type === "rest") {
    return `${event.actor_agent_id ?? "Someone"} slowed down and rested.`;
  }
  return `${event.event_type} happened in the town.`;
}

function locationBeat(
  locationId: string,
  events: NonNullable<Awaited<ReturnType<typeof getWorld>>>["recent_events"],
) {
  const matched = events.find((event) => event.location_id === locationId);
  if (!matched) {
    return "quiet";
  }
  if (matched.event_type === "talk") {
    return "conversation";
  }
  if (matched.event_type === "move") {
    return "arrival";
  }
  if (matched.event_type === "work") {
    return "working";
  }
  if (matched.event_type === "rest") {
    return "resting";
  }
  return matched.event_type;
}

function beatTone(beat: string) {
  if (beat === "conversation") return "bg-rose-100 text-rose-900";
  if (beat === "arrival") return "bg-emerald-100 text-emerald-900";
  if (beat === "working") return "bg-amber-100 text-amber-900";
  if (beat === "resting") return "bg-slate-100 text-slate-800";
  if (beat === "quiet") return "bg-white/80 text-slate-600";
  return "bg-mist text-slate-700";
}

function connectorClass(index: number) {
  const variants = [
    "left-[23%] top-[28%] w-[54%] rotate-[3deg]",
    "left-[23%] top-[62%] w-[42%] -rotate-[8deg]",
    "left-[49%] top-[28%] h-[40%] w-px",
  ];
  return variants[index % variants.length];
}

export default async function WorldPage({ params }: WorldPageProps) {
  const { runId } = await params;
  const world = await getWorld(runId);
  const latestTick = world?.recent_events[0]?.tick_no ?? world?.run.current_tick ?? 0;

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,_#f7f3e8,_#eef5f1_48%,_#f8fafc)] px-6 py-12">
      <div className="mx-auto max-w-6xl space-y-8">
        <header className="space-y-3">
          <Link href={`/runs/${runId}`} className="text-sm uppercase tracking-[0.25em] text-moss">
            Director Console
          </Link>
          <h1 className="text-5xl font-semibold text-ink">
            {world ? world.run.name : "World Viewer"}
          </h1>
          <p className="max-w-3xl text-lg text-slate-700">
            面向观众的第一版世界观看页。展示地点、当前人物分布和最近公共事件，不暴露导演控制细节。
          </p>
          {world ? (
            <WorldLiveControls tick={world.run.current_tick ?? 0} status={world.run.status} />
          ) : null}
        </header>

        {world ? (
          <>
            <SectionCard
              title="Town Layout"
              description="按地点坐标绘制的小镇视图。角色会聚集在各自当前所在地点。"
            >
              <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(320px,1fr)]">
                <div className="relative overflow-hidden rounded-[2rem] border border-slate-200 bg-[linear-gradient(180deg,_rgba(255,255,255,0.95),_rgba(238,243,234,0.82))] p-4 shadow-sm">
                  <div className="pointer-events-none absolute inset-0 opacity-60">
                    <div className="absolute inset-x-6 top-1/2 h-px border-t border-dashed border-slate-300/80" />
                    <div className="absolute inset-y-6 left-1/2 w-px border-l border-dashed border-slate-300/80" />
                    {world.locations.length > 1
                      ? world.locations.slice(0, Math.max(0, world.locations.length - 1)).map((location, index) => (
                          <div
                            key={`${location.id}-connector`}
                            className={`absolute rounded-full bg-moss/25 ${connectorClass(index)}`}
                            style={{ height: index === 2 ? "40%" : "2px" }}
                          />
                        ))
                      : null}
                  </div>

                  <div className="grid auto-rows-[240px] gap-4 md:grid-cols-2">
                    {world.locations.map((location) => (
                      (() => {
                        const beat = locationBeat(location.id, world.recent_events);
                        return (
                      <div
                        key={location.id}
                        className={`relative rounded-3xl border px-5 py-5 shadow-sm transition ${locationTone(location.location_type)}`}
                        style={{
                          gridColumnStart: Math.min(location.x + 1, 2),
                          gridRowStart: location.y + 1,
                        }}
                      >
                        <div className="absolute right-4 top-4 h-20 w-20 rounded-full bg-white/35 blur-2xl" />
                        <div className="flex items-start justify-between gap-4">
                          <div>
                            <h2 className="text-2xl font-semibold text-ink">{location.name}</h2>
                            <p className="mt-1 text-sm uppercase tracking-[0.18em] text-slate-500">
                              {location.location_type} · ({location.x}, {location.y})
                            </p>
                          </div>
                          <div className="rounded-full bg-white/80 px-3 py-1 text-xs font-medium text-slate-600">
                            {location.occupants.length}/{location.capacity}
                          </div>
                        </div>

                        <div className="mt-4 flex items-center gap-2">
                          <span className={`rounded-full px-3 py-1 text-xs font-medium uppercase tracking-[0.16em] ${beatTone(beat)}`}>
                            {beat}
                          </span>
                          {beat !== "quiet" ? (
                            <span className="text-xs uppercase tracking-[0.16em] text-slate-500">
                              live at tick {latestTick}
                            </span>
                          ) : null}
                        </div>

                        <div className="mt-5 space-y-3">
                          {location.occupants.length === 0 ? (
                            <p className="text-sm text-slate-500">这里暂时没有居民。</p>
                          ) : (
                            location.occupants.map((agent) => (
                              <Link
                                key={agent.id}
                                href={`/runs/${runId}/agents/${agent.id}`}
                                className="agent-token block rounded-2xl border border-white/80 bg-white/80 px-4 py-3 transition hover:border-moss hover:bg-white"
                              >
                                <div className="flex items-center justify-between gap-3">
                                  <div className="flex items-center gap-3">
                                    <div
                                      className={`flex h-10 w-10 items-center justify-center rounded-full text-sm font-semibold ${agentTone(agent.occupation)}`}
                                    >
                                      {initials(agent.name)}
                                    </div>
                                    <div>
                                      <span className="font-medium text-ink">{agent.name}</span>
                                      <p className="mt-0.5 text-xs uppercase tracking-[0.16em] text-slate-500">
                                        {agent.current_location_id ?? location.id}
                                      </p>
                                    </div>
                                  </div>
                                  <span className="text-xs uppercase tracking-[0.16em] text-slate-500">
                                    {agent.occupation ?? "resident"}
                                  </span>
                                </div>
                                <p className="mt-1 text-sm text-slate-600">
                                  当前目标：{agent.current_goal ?? "rest"}
                                </p>
                              </Link>
                            ))
                          )}
                        </div>
                      </div>
                        );
                      })()
                    ))}
                  </div>
                </div>

                <div className="space-y-4">
                  <div className="rounded-3xl border border-slate-200 bg-white/80 p-5 shadow-sm">
                    <div className="text-xs uppercase tracking-[0.22em] text-moss">Town Metrics</div>
                    <div className="mt-4 grid gap-3">
                      <div className="rounded-2xl bg-mist px-4 py-3">
                        <div className="text-xs uppercase tracking-[0.16em] text-slate-500">Locations</div>
                        <div className="mt-1 text-3xl font-semibold text-ink">{world.locations.length}</div>
                      </div>
                      <div className="rounded-2xl bg-mist px-4 py-3">
                        <div className="text-xs uppercase tracking-[0.16em] text-slate-500">Residents On Stage</div>
                        <div className="mt-1 text-3xl font-semibold text-ink">
                          {world.locations.reduce((count, location) => count + location.occupants.length, 0)}
                        </div>
                      </div>
                      <div className="rounded-2xl bg-mist px-4 py-3">
                        <div className="text-xs uppercase tracking-[0.16em] text-slate-500">Public Beats</div>
                        <div className="mt-1 text-3xl font-semibold text-ink">{world.recent_events.length}</div>
                      </div>
                    </div>
                  </div>

                  <div className="rounded-3xl border border-slate-200 bg-white/80 p-5 shadow-sm">
                    <div className="text-xs uppercase tracking-[0.22em] text-moss">Neighborhood Notes</div>
                    <div className="mt-4 space-y-3 text-sm text-slate-700">
                      <p>
                        这个观看页只展示公共舞台上的位置与事件，不暴露导演层注入接口和底层状态结构。
                      </p>
                      <p>
                        你可以打开自动刷新，然后在导演控制台执行 <span className="font-medium text-ink">Step Tick</span>，
                        这里会看到居民重新分布和新的剧情节拍。
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </SectionCard>

            <SectionCard title="Live Story Beats" description="更接近观众视角的叙事事件流。">
              <div className="space-y-3">
                {world.recent_events.length === 0 ? (
                  <p className="text-sm text-slate-600">世界还没有公开事件。</p>
                ) : (
                  world.recent_events.map((event) => (
                    <div
                      key={event.id}
                      className={`relative overflow-hidden rounded-2xl border px-4 py-4 ${
                        event.tick_no === latestTick
                          ? "latest-beat border-moss/40 bg-emerald-50/70 shadow-sm"
                          : "border-slate-200 bg-white"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <div className="text-xs uppercase tracking-[0.18em] text-moss">
                            Tick {event.tick_no}
                            {event.tick_no === latestTick ? " · latest" : ""}
                          </div>
                          <p className="mt-2 text-base text-ink">{describeEvent(event)}</p>
                        </div>
                        <span className="rounded-full bg-mist px-3 py-1 text-xs font-medium uppercase tracking-[0.16em] text-slate-600">
                          {event.event_type}
                        </span>
                      </div>
                      {(event.actor_agent_id || event.target_agent_id || event.location_id) ? (
                        <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-600">
                          {event.actor_agent_id ? <span>actor {event.actor_agent_id}</span> : null}
                          {event.target_agent_id ? <span>target {event.target_agent_id}</span> : null}
                          {event.location_id ? <span>location {event.location_id}</span> : null}
                        </div>
                      ) : null}
                    </div>
                  ))
                )}
              </div>
            </SectionCard>
          </>
        ) : (
          <SectionCard title="Unavailable">
            <p className="text-sm text-slate-600">未获取到 world snapshot，可能是后端未启动或 run 不存在。</p>
          </SectionCard>
        )}
      </div>
    </main>
  );
}
