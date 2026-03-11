"use client";

import { useRef, useState, useTransition } from "react";

import { injectDirectorEventResult } from "@/lib/api";

type DirectorEventFormProps = {
  runId: string;
  onInjected?: () => void;
  compact?: boolean;
  locations?: Array<{ id: string; name: string; location_type: string }>;
};

const EVENT_OPTIONS = [
  {
    value: "broadcast",
    label: "广播",
    needsLocation: false,
    placeholder: "输入要广播给居民的消息...",
    hint: "向全局投递一个导演提示",
    badge: "全局",
    accent: "from-slate-700 via-slate-700 to-slate-600",
    glow: "shadow-slate-200/60",
  },
  {
    value: "activity",
    label: "活动",
    needsLocation: true,
    placeholder: "输入活动内容...",
    hint: "推动某个地点形成事件或聚集",
    badge: "地点",
    accent: "from-amber-600 via-amber-500 to-orange-500",
    glow: "shadow-amber-200/60",
  },
  {
    value: "shutdown",
    label: "地点关闭",
    needsLocation: true,
    placeholder: "输入关闭说明...",
    hint: "让角色围绕关闭状态自然反应",
    badge: "限制",
    accent: "from-stone-600 via-stone-500 to-amber-600",
    glow: "shadow-stone-200/60",
  },
  {
    value: "weather_change",
    label: "天气变化",
    needsLocation: false,
    placeholder: "输入天气变化说明...",
    hint: "注入环境变化，影响后续判断",
    badge: "环境",
    accent: "from-sky-600 via-sky-500 to-cyan-500",
    glow: "shadow-sky-200/60",
  },
  {
    value: "power_outage",
    label: "停电",
    needsLocation: true,
    placeholder: "输入停电影响说明...",
    hint: "制造公共异常，测试群体反应链路",
    badge: "异常",
    accent: "from-moss via-emerald-600 to-teal-600",
    glow: "shadow-emerald-200/60",
  },
] as const;

const PRESET_MESSAGES: Record<string, string[]> = {
  broadcast: ["广场集合", "停电通知", "市集营业", "电影放映"],
  activity: ["广场演出", "咖啡馆活动", "海边集市"],
  shutdown: ["医院临时关闭", "码头暂停开放", "广场维护中"],
  weather_change: ["突发大雨", "海风增强", "傍晚降温"],
  power_outage: ["广场停电", "咖啡馆停电", "街区停电"],
};

export function DirectorEventForm({
  runId,
  onInjected,
  compact,
  locations = [],
}: DirectorEventFormProps) {
  const [eventType, setEventType] = useState<(typeof EVENT_OPTIONS)[number]["value"]>("broadcast");
  const [message, setMessage] = useState("Town hall at plaza");
  const [locationId, setLocationId] = useState("");
  const [statusMessage, setStatusMessage] = useState("");
  const [isPending, startTransition] = useTransition();
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const eventOption = EVENT_OPTIONS.find((item) => item.value === eventType) ?? EVENT_OPTIONS[0];
  const presets = PRESET_MESSAGES[eventType] ?? PRESET_MESSAGES.broadcast;
  const selectedLocation = locations.find((l) => l.id === locationId);
  const isSubmitDisabled = isPending || (eventOption.needsLocation && !locationId);

  return (
    <form
      className={compact ? "space-y-3" : "space-y-5"}
      onSubmit={(event) => {
        event.preventDefault();
        startTransition(async () => {
          const result = await injectDirectorEventResult(runId, {
            event_type: eventType,
            payload: { message },
            location_id: locationId || undefined,
            importance: 0.8,
          });
          setStatusMessage(
            result.data
              ? "已注入"
              : result.error === "network_error"
                ? "后端不可达"
                : "注入失败",
          );
          if (result.data) {
            onInjected?.();
          }
          setTimeout(() => setStatusMessage(""), 3000);
        });
      }}
    >
      {/* 标题 + 预设 */}
      {!compact && (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className="text-base font-medium text-ink">导演干预</span>
            <span className="rounded-full bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-600">
              {eventOption.label}
            </span>
          </div>
          <div className="flex flex-wrap gap-2">
            {presets.map((preset) => (
              <button
                key={preset}
                type="button"
                onClick={() => setMessage(preset)}
                className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-600 transition hover:border-moss hover:bg-moss/5 hover:text-moss"
              >
                {preset}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* 表单字段 */}
      <div className="space-y-3">
        <div className="space-y-2">
          <label className="block">
            <span className="text-sm font-medium text-slate-600">事件类型</span>
          </label>
          {compact ? (
            <div className="flex flex-wrap gap-1.5">
              {EVENT_OPTIONS.map((option) => {
                const isActive = option.value === eventType;
                return (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => {
                      setEventType(option.value);
                      setMessage(PRESET_MESSAGES[option.value]?.[0] ?? "");
                      if (!option.needsLocation) {
                        setLocationId("");
                      }
                    }}
                    className={`rounded-full border px-3 py-1.5 text-xs font-medium transition ${
                      isActive
                        ? `border-transparent bg-gradient-to-r ${option.accent} text-white shadow-sm`
                        : "border-slate-200 bg-white text-slate-500 hover:border-slate-300 hover:text-slate-700"
                    }`}
                  >
                    {option.label}
                  </button>
                );
              })}
            </div>
          ) : (
            <div className="grid gap-2 grid-cols-1 sm:grid-cols-2">
              {EVENT_OPTIONS.map((option) => {
                const isActive = option.value === eventType;
                return (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => {
                      setEventType(option.value);
                      setMessage(PRESET_MESSAGES[option.value]?.[0] ?? "");
                      if (!option.needsLocation) {
                        setLocationId("");
                      }
                    }}
                    className={`group relative overflow-hidden rounded-[20px] border px-4 py-3 text-left transition ${
                      isActive
                        ? "border-transparent bg-white shadow-md"
                        : "border-slate-200/90 bg-white/85 hover:border-slate-300 hover:bg-white"
                    }`}
                  >
                    <div
                      className={`absolute inset-x-0 top-0 h-1 bg-gradient-to-r ${option.accent} transition-opacity ${
                        isActive ? "opacity-100" : "opacity-40 group-hover:opacity-70"
                      }`}
                    />
                    <div className="relative flex items-start justify-between gap-3">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-semibold text-slate-800">{option.label}</span>
                          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium uppercase tracking-[0.16em] text-slate-500">
                            {option.badge}
                          </span>
                        </div>
                        <p className="text-xs leading-5 text-slate-500">{option.hint}</p>
                      </div>
                      <span
                        className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border text-[11px] transition ${
                          isActive
                            ? `border-white/70 bg-gradient-to-br ${option.accent} text-white shadow-sm ${option.glow}`
                            : "border-slate-200 bg-white text-transparent group-hover:text-slate-300"
                        }`}
                      >
                        ●
                      </span>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>
        {eventOption.needsLocation && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-500">影响地点</span>
              {selectedLocation && (
                <span className="text-xs text-slate-400">{selectedLocation.name}</span>
              )}
            </div>
            <div className="flex flex-wrap gap-1.5">
              {locations.map((location) => {
                const isActive = location.id === locationId;
                return (
                  <button
                    key={location.id}
                    type="button"
                    onClick={() => setLocationId(location.id)}
                    className={`rounded-full border px-3 py-1.5 text-xs font-medium transition ${
                      isActive
                        ? "border-transparent bg-slate-700 text-white shadow-sm"
                        : "border-slate-200 bg-white text-slate-500 hover:border-slate-300 hover:text-slate-700"
                    }`}
                  >
                    {location.name}
                  </button>
                );
              })}
              {locations.length === 0 && (
                <span className="text-xs text-slate-400">暂无可用地点</span>
              )}
            </div>
          </div>
        )}
        <div className="relative">
          {compact && (
            <span className="absolute left-3 top-2 text-[10px] font-medium text-slate-400 select-none pointer-events-none">
              内容
            </span>
          )}
          {!compact && (
            <label className="mb-1.5 block text-xs font-medium text-slate-500">事件内容</label>
          )}
          <textarea
            ref={textareaRef}
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            rows={compact ? 2 : 4}
            className={`w-full resize-none rounded-xl border border-slate-200 bg-white text-sm leading-relaxed outline-hidden transition placeholder:text-slate-400 hover:border-slate-300 focus:border-moss focus:ring-2 focus:ring-moss/10 ${
              compact ? "px-3 pt-5 pb-2" : "px-3 py-2"
            }`}
            placeholder={eventOption.placeholder}
          />
        </div>
      </div>

      {/* 预设按钮（紧凑模式） */}
      {compact && (
        <div className="flex flex-wrap gap-1.5">
          {presets.map((preset) => (
            <button
              key={preset}
              type="button"
              onClick={() => setMessage(preset)}
              className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs text-slate-500 transition hover:border-moss/40 hover:bg-moss/5 hover:text-moss"
            >
              {preset}
            </button>
          ))}
        </div>
      )}

      {/* 提交 + 状态 */}
      <div className={`flex items-center gap-3 ${compact ? "" : "pt-2"}`}>
        <button
          type="submit"
          disabled={isSubmitDisabled}
          className={`rounded-full bg-ember font-medium text-white shadow-xs transition hover:bg-ember/90 hover:shadow-sm disabled:opacity-50 ${
            compact ? "flex-1 py-2 text-xs" : "px-6 py-2.5 text-sm"
          }`}
        >
          {isPending ? "注入中..." : "注入事件"}
        </button>
        {statusMessage && (
          <span className={`text-xs font-medium ${
            statusMessage === "已注入" ? "text-emerald-600" : "text-red-500"
          }`}>
            {statusMessage === "已注入" ? "✓ " : "✗ "}{statusMessage}
          </span>
        )}
      </div>
    </form>
  );
}
