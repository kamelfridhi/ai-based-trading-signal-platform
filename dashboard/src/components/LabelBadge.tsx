import type { SignalLabel } from "../api/types";

const styles: Record<SignalLabel, string> = {
  BUY: "bg-emerald-500/20 text-emerald-300 ring-emerald-400/40",
  SELL: "bg-rose-500/20 text-rose-300 ring-rose-400/40",
  HOLD: "bg-amber-500/15 text-amber-200 ring-amber-400/30",
};

export function LabelBadge({ label }: { label: SignalLabel }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide ring-1 ${styles[label]}`}
    >
      {label}
    </span>
  );
}
