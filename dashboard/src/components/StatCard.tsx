import type { ReactNode } from "react";

interface StatCardProps {
  title: string;
  value: ReactNode;
  subtitle?: string;
  icon?: ReactNode;
  accent?: string;
}

export function StatCard({
  title,
  value,
  subtitle,
  icon,
  accent = "from-cyan-500/20 to-violet-500/10",
}: StatCardProps) {
  return (
    <div className="glass-panel relative overflow-hidden p-5">
      <div
        className={`pointer-events-none absolute inset-0 bg-gradient-to-br ${accent} opacity-60`}
      />
      <div className="relative flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-wider text-slate-400">
            {title}
          </p>
          <p className="mt-2 font-mono text-2xl font-semibold text-white">
            {value}
          </p>
          {subtitle ? (
            <p className="mt-1 text-sm text-slate-400">{subtitle}</p>
          ) : null}
        </div>
        {icon ? (
          <div className="rounded-xl bg-white/5 p-2 text-accent-cyan">{icon}</div>
        ) : null}
      </div>
    </div>
  );
}
