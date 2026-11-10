import { useMutation } from "@tanstack/react-query";
import { Loader2, Search } from "lucide-react";
import { useState } from "react";

import { api } from "../api/client";
import type { SymbolInsight } from "../api/types";
import { ConfidenceBar } from "./ConfidenceBar";
import { LabelBadge } from "./LabelBadge";

const EXAMPLES = ["AAPL", "MSFT", "GOOGL", "TSLA", "BTC-USD", "ETH-USD", "EUR-USD"];

function fmtNum(v: number | null | undefined, digits = 2) {
  if (v == null || Number.isNaN(v)) return "—";
  return v.toFixed(digits);
}

export function SymbolLookup() {
  const [input, setInput] = useState("AAPL");
  const [insight, setInsight] = useState<SymbolInsight | null>(null);

  const lookup = useMutation({
    mutationFn: (symbol: string) => api.analyzeSymbol(symbol, { persist: true }),
    onSuccess: (data) => setInsight(data),
  });

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const sym = input.trim();
    if (!sym) return;
    lookup.mutate(sym);
  };

  const pred = insight?.prediction;
  const tech = insight?.technicals ?? {};
  const sent = insight?.sentiment;

  return (
    <div className="glass-panel p-5">
      <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
        Symbol lookup
      </h2>
      <p className="mt-1 text-sm text-slate-500">
        Enter a ticker or pair for a live prediction and analytics.
      </p>

      <form onSubmit={onSubmit} className="mt-4 flex flex-wrap gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value.toUpperCase())}
          placeholder="e.g. AAPL, BTC-USD"
          className="min-w-[200px] flex-1 rounded-xl border border-white/10 bg-surface-800/80 px-4 py-2.5 font-mono text-sm text-white outline-none ring-cyan-500/30 focus:ring-2"
          list="symbol-suggestions"
        />
        <datalist id="symbol-suggestions">
          {EXAMPLES.map((s) => (
            <option key={s} value={s} />
          ))}
        </datalist>
        <button
          type="submit"
          disabled={lookup.isPending}
          className="inline-flex items-center gap-2 rounded-xl bg-cyan-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-cyan-500 disabled:opacity-50"
        >
          {lookup.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Search className="h-4 w-4" />
          )}
          Analyze
        </button>
      </form>

      <div className="mt-3 flex flex-wrap gap-2">
        {EXAMPLES.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => {
              setInput(s);
              lookup.mutate(s);
            }}
            className="rounded-lg border border-white/10 px-2.5 py-1 text-xs text-slate-400 hover:border-cyan-500/40 hover:text-cyan-200"
          >
            {s}
          </button>
        ))}
      </div>

      {lookup.isError ? (
        <p className="mt-4 text-sm text-rose-300">
          {(lookup.error as Error).message}
        </p>
      ) : null}

      {insight && pred ? (
        <div className="mt-6 space-y-5 border-t border-white/10 pt-5">
          <div className="flex flex-wrap items-center gap-4">
            <span className="text-2xl font-bold text-white">{insight.symbol}</span>
            <LabelBadge label={pred.predicted_label} />
            <span className="font-mono text-lg text-cyan-300">
              {(pred.confidence * 100).toFixed(1)}% confidence
            </span>
            {!pred.meets_threshold ? (
              <span className="text-xs text-amber-300/90">
                Below {(pred.confidence_threshold * 100).toFixed(0)}% threshold — still shown
              </span>
            ) : null}
          </div>

          <ConfidenceBar
            buy={pred.prob_buy}
            sell={pred.prob_sell}
            hold={pred.prob_hold}
          />

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Metric label="Price" value={fmtNum(insight.price?.close ?? tech.close)} />
            <Metric label="RSI (14)" value={fmtNum(tech.rsi_14)} />
            <Metric label="Return 1h" value={`${fmtNum(tech.return_1)}%`} />
            <Metric label="MACD" value={fmtNum(tech.macd, 4)} />
            <Metric label="SMA 20" value={fmtNum(tech.sma_20)} />
            <Metric label="Vol change" value={`${fmtNum(tech.volume_change_pct)}%`} />
            <Metric label="News (1h)" value={sent?.news_count_1h ?? "—"} />
            <Metric
              label="Sentiment avg"
              value={fmtNum(sent?.news_sentiment_avg_1h, 3)}
            />
          </div>

          {insight.recent_news.length > 0 ? (
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Recent news
              </h3>
              <ul className="mt-2 space-y-2">
                {insight.recent_news.map((n, i) => (
                  <li
                    key={i}
                    className="rounded-lg border border-white/5 bg-surface-800/40 px-3 py-2 text-sm"
                  >
                    <span className="text-slate-300">{n.title}</span>
                    <span className="ml-2 text-xs text-slate-500">
                      {n.sentiment_label}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          <p className="text-xs text-slate-600">
            As of {new Date(insight.as_of).toLocaleString()}
            {insight.persisted_signal ? " · saved to trading_signals" : ""}
          </p>
        </div>
      ) : null}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl bg-surface-800/50 px-3 py-2">
      <p className="text-[10px] uppercase tracking-wider text-slate-500">{label}</p>
      <p className="mt-1 font-mono text-sm text-slate-200">{value}</p>
    </div>
  );
}
