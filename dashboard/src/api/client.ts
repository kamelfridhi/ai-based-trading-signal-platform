import type {
  HealthResponse,
  LatestPrice,
  ModelRun,
  PipelineJob,
  SymbolInsight,
  TradingSignal,
} from "./types";

const BASE = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    const text = await res.text();
    try {
      const body = JSON.parse(text) as { detail?: string | { msg: string }[] };
      if (typeof body.detail === "string") {
        if (res.status === 404 && body.detail === "Not Found") {
          throw new Error(
            "API endpoint missing — stop and restart: python -m src.api.run_server",
          );
        }
        throw new Error(body.detail);
      }
    } catch (e) {
      if (e instanceof Error && e.message.includes("restart")) throw e;
    }
    throw new Error(text || res.statusText);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<HealthResponse>("/health"),
  latestSignals: () => request<TradingSignal[]>("/api/v1/signals/latest"),
  listSignals: (limit = 50) =>
    request<TradingSignal[]>(`/api/v1/signals?limit=${limit}`),
  latestPrices: () => request<LatestPrice[]>("/api/v1/prices/latest"),
  latestModel: () => request<ModelRun>("/api/v1/models/latest"),
  startTrain: () =>
    request<PipelineJob>("/api/v1/pipeline/train", { method: "POST" }),
  startPredict: (modelRunId?: number) =>
    request<PipelineJob>("/api/v1/pipeline/predict", {
      method: "POST",
      body: JSON.stringify({ model_run_id: modelRunId ?? null }),
    }),
  getJob: (jobId: string) =>
    request<PipelineJob>(`/api/v1/pipeline/jobs/${jobId}`),
  analyzeSymbol: (symbol: string, opts?: { persist?: boolean; modelRunId?: number }) =>
    request<SymbolInsight>("/api/v1/analytics/lookup", {
      method: "POST",
      body: JSON.stringify({
        symbol: symbol.trim().toUpperCase(),
        model_run_id: opts?.modelRunId ?? null,
        persist: opts?.persist ?? false,
      }),
    }),
};
