export const WORLD_VIEWS = ["director", "stage", "3d"] as const;

export type WorldView = (typeof WORLD_VIEWS)[number];

export function isWorldView(value: string | null): value is WorldView {
  return value !== null && WORLD_VIEWS.includes(value as WorldView);
}

type Props = {
  currentView: WorldView;
  onToggle: (view: WorldView) => void;
};

export function WorldViewToggle({ currentView, onToggle }: Props) {
  return (
    <div
      role="group"
      aria-label="世界视图"
      className="flex items-center rounded-xl bg-white/95 p-1 shadow-[0_2px_8px_rgba(15,23,42,0.12)]"
    >
      <button
        type="button"
        aria-pressed={currentView === "director"}
        onClick={() => onToggle("director")}
        className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-900 ${
          currentView === "director"
            ? "bg-slate-900 text-white"
            : "text-slate-500 hover:bg-slate-100 hover:text-slate-800"
        }`}
      >
        导演地图
      </button>
      <button
        type="button"
        aria-pressed={currentView === "stage"}
        onClick={() => onToggle("stage")}
        className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 ${
          currentView === "stage"
            ? "bg-emerald-600 text-white"
            : "text-slate-500 hover:bg-slate-100 hover:text-slate-800"
        }`}
      >
        舞台视图
      </button>
      <button
        type="button"
        aria-pressed={currentView === "3d"}
        onClick={() => onToggle("3d")}
        className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-700 ${
          currentView === "3d"
            ? "bg-sky-600 text-white"
            : "text-slate-500 hover:bg-slate-100 hover:text-slate-800"
        }`}
      >
        3D 世界
      </button>
    </div>
  );
}
