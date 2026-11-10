interface ConfidenceBarProps {
  buy: number;
  sell: number;
  hold: number;
}

export function ConfidenceBar({ buy, sell, hold }: ConfidenceBarProps) {
  const total = buy + sell + hold || 1;
  const wBuy = (buy / total) * 100;
  const wSell = (sell / total) * 100;
  const wHold = (hold / total) * 100;

  return (
    <div className="flex h-2 w-full overflow-hidden rounded-full bg-surface-800">
      <div
        className="bg-emerald-400/80 transition-all"
        style={{ width: `${wBuy}%` }}
        title={`BUY ${(buy * 100).toFixed(1)}%`}
      />
      <div
        className="bg-rose-400/80 transition-all"
        style={{ width: `${wSell}%` }}
        title={`SELL ${(sell * 100).toFixed(1)}%`}
      />
      <div
        className="bg-amber-400/70 transition-all"
        style={{ width: `${wHold}%` }}
        title={`HOLD ${(hold * 100).toFixed(1)}%`}
      />
    </div>
  );
}
