export type WorldView = "svg" | "voxel";

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
        aria-pressed={currentView === "svg"}
        onClick={() => onToggle("svg")}
        className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-900 ${
          currentView === "svg"
            ? "bg-slate-900 text-white"
            : "text-slate-500 hover:bg-slate-100 hover:text-slate-800"
        }`}
      >
        导演地图
      </button>
      <button
        type="button"
        aria-pressed={currentView === "voxel"}
        onClick={() => onToggle("voxel")}
        className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 ${
          currentView === "voxel"
            ? "bg-emerald-600 text-white"
            : "text-slate-500 hover:bg-slate-100 hover:text-slate-800"
        }`}
      >
        舞台视图
      </button>
    </div>
  );
}
