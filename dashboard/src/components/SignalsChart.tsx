import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { TradingSignal } from "../api/types";

export function SignalsChart({ signals }: { signals: TradingSignal[] }) {
  const data = signals.map((s) => ({
    symbol: s.symbol.replace("-USD", ""),
    confidence: Number((s.confidence * 100).toFixed(1)),
    label: s.predicted_label,
  }));

  if (!data.length) {
    return (
      <div className="flex h-64 items-center justify-center text-sm text-slate-500">
        No signals to chart
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: -8, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
        <XAxis
          dataKey="symbol"
          tick={{ fill: "#94a3b8", fontSize: 12 }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          domain={[0, 100]}
          tick={{ fill: "#64748b", fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          unit="%"
        />
        <Tooltip
          contentStyle={{
            background: "#151d2e",
            border: "1px solid rgba(255,255,255,0.1)",
            borderRadius: 12,
          }}
          formatter={(value: number, _name, item) => [
            `${value}%`,
            `${item.payload.label}`,
          ]}
        />
        <Bar dataKey="confidence" fill="#22d3ee" radius={[6, 6, 0, 0]} maxBarSize={48} />
      </BarChart>
    </ResponsiveContainer>
  );
}
