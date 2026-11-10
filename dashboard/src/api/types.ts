export type SignalLabel = "BUY" | "SELL" | "HOLD";

export interface TradingSignal {
  id: number;
  model_run_id: number;
  symbol: string;
  timestamp: string;
  predicted_label: SignalLabel;
  prob_buy: number;
  prob_sell: number;
  prob_hold: number;
  confidence: number;
  created_at: string;
}

export interface LatestPrice {
  symbol: string;
  close: number;
  timestamp: string;
}

export interface ModelRun {
  id: number;
  model_path: string;
  macro_f1: number | null;
  metrics: Record<string, unknown>;
  trained_at: string;
}

export interface HealthResponse {
  status: string;
  database: string;
}

export type JobStatus = "queued" | "running" | "completed" | "failed";

export interface SymbolInsight {
  symbol: string;
  as_of: string;
  price: { close: number; timestamp: string } | null;
  prediction: {
    predicted_label: SignalLabel;
    confidence: number;
    prob_buy: number;
    prob_sell: number;
    prob_hold: number;
    meets_threshold: boolean;
    confidence_threshold: number;
    model_run_id: number;
  };
  technicals: Record<string, number | undefined>;
  sentiment: {
    news_count_1h: number | null;
    news_sentiment_avg_1h: number | null;
  };
  recent_news: {
    title: string;
    sentiment_label: string | null;
    sentiment_value: number | null;
    published_at: string;
  }[];
  persisted_signal: boolean;
}

export interface PipelineJob {
  job_id: string;
  job_type: "train" | "predict";
  status: JobStatus;
  created_at?: string;
  started_at?: string | null;
  finished_at?: string | null;
  result?: Record<string, unknown> | null;
  error?: string | null;
}
