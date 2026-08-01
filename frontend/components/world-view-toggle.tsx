export type WorldView = "svg" | "voxel";

type Props = {
  currentView: WorldView;
  onToggle: (view: WorldView) => void;
};

export function WorldViewToggle({ currentView, onToggle }: Props) {
  return (
    <div className="flex items-center gap-2 rounded-2xl border border-slate-200 bg-white/80 p-1 shadow-xs">
      <button
        type="button"
        aria-pressed={currentView === "svg"}
        onClick={() => onToggle("svg")}
        className={`rounded-xl px-3 py-1.5 text-sm font-medium transition ${
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
        className={`rounded-xl px-3 py-1.5 text-sm font-medium transition ${
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
