type MetricChipProps = {
  label: string;
  value: string | number;
};

export function MetricChip({ label, value }: MetricChipProps) {
  return (
    <div className="rounded-3xl border border-slate-200 bg-[linear-gradient(180deg,rgba(255,255,255,0.92),rgba(238,243,234,0.9))] px-4 py-4 shadow-xs">
      <div className="text-xs uppercase tracking-[0.2em] text-moss">{label}</div>
      <div className="mt-2 text-lg font-semibold text-ink">{value}</div>
    </div>
  );
}
