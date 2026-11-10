import { Brain, CheckCircle2, Loader2, Sparkles, XCircle } from "lucide-react";
import { useCallback, useState } from "react";

import { api } from "../api/client";
import type { PipelineJob } from "../api/types";

const statusStyles = {
  queued: "text-slate-400",
  running: "text-cyan-300",
  completed: "text-emerald-300",
  failed: "text-rose-300",
} as const;

function formatPct(value: unknown) {
  if (typeof value !== "number") return "—";
  return `${(value * 100).toFixed(1)}%`;
}

function formatF1(value: unknown) {
  if (typeof value !== "number") return "—";
  return value.toFixed(4);
}

function JobResultCard({ job }: { job: PipelineJob | null }) {
  const [showRaw, setShowRaw] = useState(false);
  if (!job) return null;

  const statusClass = statusStyles[job.status] ?? "text-slate-300";
  const result = job.result;

  return (
    <div className="mt-4 rounded-xl border border-white/10 bg-surface-800/60 p-4 text-sm">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          {job.status === "completed" ? (
            <CheckCircle2 className="h-4 w-4 text-emerald-400" />
          ) : job.status === "failed" ? (
            <XCircle className="h-4 w-4 text-rose-400" />
          ) : (
            <Loader2 className="h-4 w-4 animate-spin text-cyan-400" />
          )}
          <span className={`font-semibold uppercase tracking-wide ${statusClass}`}>
            {job.job_type} · {job.status}
          </span>
        </div>
        <span className="font-mono text-xs text-slate-500">{job.job_id.slice(0, 8)}…</span>
      </div>

      {job.status === "running" || job.status === "queued" ? (
        <p className="mt-3 text-slate-400">
          {job.job_type === "train"
            ? "Training the BiLSTM model… this may take a minute."
            : "Running inference and writing signals…"}
        </p>
      ) : null}

      {job.error ? <p className="mt-3 text-rose-300">{job.error}</p> : null}

      {job.status === "completed" && result && job.job_type === "train" ? (
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <ResultMetric label="Model run ID" value={`#${result.model_run_id ?? "—"}`} />
          <ResultMetric label="Macro F1" value={formatF1(result.macro_f1)} />
          <ResultMetric label="Test accuracy" value={formatPct(result.accuracy)} />
          <ResultMetric
            label="Checkpoint"
            value={
              typeof result.checkpoint_path === "string"
                ? result.checkpoint_path.split(/[/\\]/).pop() ?? "saved"
                : "saved"
            }
            title={
              typeof result.checkpoint_path === "string"
                ? result.checkpoint_path
                : undefined
            }
          />
        </div>
      ) : null}

      {job.status === "completed" && result && job.job_type === "predict" ? (
        <div className="mt-4">
          <p className="text-base text-white">
            <span className="font-semibold text-cyan-300">
              {typeof result.signals_written === "number" ? result.signals_written : 0}
            </span>{" "}
            signal(s) saved
          </p>
          <p className="mt-1 text-slate-500">
            Only symbols with confidence ≥ 80% are written to the database. Refresh the
            table below or use Symbol lookup.
          </p>
        </div>
      ) : null}

      {result && job.status === "completed" ? (
        <button
          type="button"
          onClick={() => setShowRaw((v) => !v)}
          className="mt-3 text-xs text-slate-500 underline-offset-2 hover:text-slate-400 hover:underline"
        >
          {showRaw ? "Hide technical JSON" : "Show technical JSON"}
        </button>
      ) : null}

      {showRaw && result ? (
        <pre className="mt-2 max-h-40 overflow-auto rounded-lg bg-black/30 p-2 font-mono text-[11px] text-slate-400">
          {JSON.stringify(result, null, 2)}
        </pre>
      ) : null}
    </div>
  );
}

function ResultMetric({
  label,
  value,
  title,
}: {
  label: string;
  value: string;
  title?: string;
}) {
  return (
    <div className="rounded-lg bg-surface-900/50 px-3 py-2" title={title}>
      <p className="text-[10px] uppercase tracking-wider text-slate-500">{label}</p>
      <p className="mt-1 font-mono text-sm text-slate-100">{value}</p>
    </div>
  );
}

async function pollJob(jobId: string, onUpdate: (j: PipelineJob) => void) {
  const terminal = new Set(["completed", "failed"]);
  for (let i = 0; i < 120; i++) {
    const job = await api.getJob(jobId);
    onUpdate(job);
    if (terminal.has(job.status)) return job;
    await new Promise((r) => setTimeout(r, 2000));
  }
  throw new Error("Job polling timed out");
}

interface PipelinePanelProps {
  onComplete: () => void;
}

export function PipelinePanel({ onComplete }: PipelinePanelProps) {
  const [busy, setBusy] = useState<"train" | "predict" | null>(null);
  const [job, setJob] = useState<PipelineJob | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(
    async (type: "train" | "predict") => {
      setError(null);
      setJob(null);
      setBusy(type);
      try {
        const started =
          type === "train" ? await api.startTrain() : await api.startPredict();
        setJob(started);
        const finished = await pollJob(started.job_id, setJob);
        if (finished.status === "completed") onComplete();
      } catch (e) {
        setError(e instanceof Error ? e.message : "Pipeline failed");
      } finally {
        setBusy(null);
      }
    },
    [onComplete],
  );

  return (
    <div className="glass-panel p-5">
      <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
        ML pipeline
      </h2>
      <p className="mt-1 text-sm text-slate-500">
        Run training or refresh signals via the API (background jobs).
      </p>
      <div className="mt-4 flex flex-wrap gap-3">
        <button
          type="button"
          disabled={busy !== null}
          onClick={() => run("predict")}
          className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-cyan-600 to-cyan-500 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-cyan-900/30 transition hover:brightness-110 disabled:opacity-50"
        >
          {busy === "predict" ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Sparkles className="h-4 w-4" />
          )}
          Run predict
        </button>
        <button
          type="button"
          disabled={busy !== null}
          onClick={() => run("train")}
          className="inline-flex items-center gap-2 rounded-xl border border-violet-400/40 bg-violet-500/15 px-4 py-2.5 text-sm font-semibold text-violet-100 transition hover:bg-violet-500/25 disabled:opacity-50"
        >
          {busy === "train" ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Brain className="h-4 w-4" />
          )}
          Run train
        </button>
      </div>
      {error ? <p className="mt-3 text-sm text-rose-300">{error}</p> : null}
      <JobResultCard job={job} />
    </div>
  );
}
