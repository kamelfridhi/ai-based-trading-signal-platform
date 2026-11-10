import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  Database,
  LineChart,
  RefreshCw,
  TrendingUp,
  Wifi,
  WifiOff,
} from "lucide-react";

import { api } from "./api/client";
import { ConfidenceBar } from "./components/ConfidenceBar";
import { LabelBadge } from "./components/LabelBadge";
import { PipelinePanel } from "./components/PipelinePanel";
import { SignalsChart } from "./components/SignalsChart";
import { SymbolLookup } from "./components/SymbolLookup";
import { StatCard } from "./components/StatCard";

function formatTime(iso: string) {
  return new Date(iso).toLocaleString();
}

function formatPrice(n: number) {
  return n >= 100 ? n.toFixed(2) : n.toFixed(4);
}

export default function App() {
  const queryClient = useQueryClient();

  const health = useQuery({ queryKey: ["health"], queryFn: api.health });
  const signals = useQuery({ queryKey: ["signals"], queryFn: api.latestSignals });
  const prices = useQuery({ queryKey: ["prices"], queryFn: api.latestPrices });
  const model = useQuery({ queryKey: ["model"], queryFn: api.latestModel });

  const online = health.data?.status === "ok" && health.data?.database === "ok";
  const signalList = signals.data ?? [];
  const priceMap = new Map((prices.data ?? []).map((p) => [p.symbol, p]));

  const avgConfidence =
    signalList.length > 0
      ? signalList.reduce((a, s) => a + s.confidence, 0) / signalList.length
      : 0;

  const labelCounts = signalList.reduce(
    (acc, s) => {
      acc[s.predicted_label] += 1;
      return acc;
    },
    { BUY: 0, SELL: 0, HOLD: 0 },
  );

  const refreshAll = () => {
    void queryClient.invalidateQueries();
  };

  return (
    <div className="min-h-screen">
      <header className="border-b border-white/5 bg-surface-900/50 backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="rounded-xl bg-gradient-to-br from-cyan-500/30 to-violet-500/30 p-2.5">
              <LineChart className="h-6 w-6 text-cyan-300" />
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-tight text-white">
                Trading Signal Platform
              </h1>
              <p className="text-xs text-slate-500">
                BiLSTM · FinBERT · Live API feed
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span
              className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ring-1 ${
                online
                  ? "bg-emerald-500/10 text-emerald-300 ring-emerald-500/30"
                  : "bg-rose-500/10 text-rose-300 ring-rose-500/30"
              }`}
            >
              {online ? <Wifi className="h-3.5 w-3.5" /> : <WifiOff className="h-3.5 w-3.5" />}
              {online ? "API connected" : "API offline"}
            </span>
            <button
              type="button"
              onClick={refreshAll}
              className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 transition hover:bg-white/10"
            >
              <RefreshCw className="h-4 w-4" />
              Refresh
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl space-y-6 px-6 py-8">
        {(signals.error || health.error) && (
          <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
            Start the API: <code className="font-mono">python -m src.api.run_server</code>
          </div>
        )}

        <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            title="Active signals"
            value={signalList.length}
            subtitle={`B ${labelCounts.BUY} · S ${labelCounts.SELL} · H ${labelCounts.HOLD}`}
            icon={<Activity className="h-5 w-5" />}
          />
          <StatCard
            title="Avg confidence"
            value={`${(avgConfidence * 100).toFixed(1)}%`}
            subtitle="Threshold ≥ 80%"
            icon={<TrendingUp className="h-5 w-5" />}
            accent="from-emerald-500/15 to-cyan-500/10"
          />
          <StatCard
            title="Model macro F1"
            value={
              model.data?.macro_f1 != null
                ? model.data.macro_f1.toFixed(3)
                : "—"
            }
            subtitle={
              model.data
                ? `Run #${model.data.id} · ${formatTime(model.data.trained_at)}`
                : "No model run"
            }
            icon={<Database className="h-5 w-5" />}
            accent="from-violet-500/15 to-fuchsia-500/10"
          />
          <StatCard
            title="Tracked symbols"
            value={prices.data?.length ?? "—"}
            subtitle="Latest market_events"
            icon={<LineChart className="h-5 w-5" />}
          />
        </section>

        <SymbolLookup />

        <section className="grid gap-6 lg:grid-cols-3">
          <div className="glass-panel lg:col-span-2 p-5">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
              Confidence by symbol
            </h2>
            <div className="mt-4">
              <SignalsChart signals={signalList} />
            </div>
          </div>
          <PipelinePanel onComplete={refreshAll} />
        </section>

        <section className="glass-panel overflow-hidden">
          <div className="border-b border-white/5 px-5 py-4">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
              Latest signals
            </h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead className="bg-surface-800/50 text-xs uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="px-5 py-3 font-medium">Symbol</th>
                  <th className="px-5 py-3 font-medium">Price</th>
                  <th className="px-5 py-3 font-medium">Signal</th>
                  <th className="px-5 py-3 font-medium">Confidence</th>
                  <th className="px-5 py-3 font-medium">Probabilities</th>
                  <th className="px-5 py-3 font-medium">As of</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {signalList.map((s) => {
                  const price = priceMap.get(s.symbol);
                  return (
                    <tr
                      key={s.id}
                      className="transition hover:bg-white/[0.02]"
                    >
                      <td className="px-5 py-4 font-semibold text-white">
                        {s.symbol}
                      </td>
                      <td className="px-5 py-4 font-mono text-slate-300">
                        {price ? `$${formatPrice(price.close)}` : "—"}
                      </td>
                      <td className="px-5 py-4">
                        <LabelBadge label={s.predicted_label} />
                      </td>
                      <td className="px-5 py-4 font-mono text-cyan-300">
                        {(s.confidence * 100).toFixed(1)}%
                      </td>
                      <td className="min-w-[200px] px-5 py-4">
                        <ConfidenceBar
                          buy={s.prob_buy}
                          sell={s.prob_sell}
                          hold={s.prob_hold}
                        />
                      </td>
                      <td className="px-5 py-4 text-slate-500">
                        {formatTime(s.timestamp)}
                      </td>
                    </tr>
                  );
                })}
                {!signalList.length && !signals.isLoading ? (
                  <tr>
                    <td
                      colSpan={6}
                      className="px-5 py-12 text-center text-slate-500"
                    >
                      No high-confidence signals yet. Run predict from the panel.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </section>
      </main>
    </div>
  );
}
