"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { Card, EmptyState } from "@/components/ui";

interface EvalResult {
  overall_mae: number;
  overall_correlation: number;
  evidence_precision: number;
  evidence_recall: number;
  evidence_f1: number;
  runs: { call_id: string; scenario: string }[];
}

export default function EvaluationsPage() {
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<EvalResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setRunning(true);
    setError(null);
    try {
      const res = await api.runEval({});
      setResult(res as EvalResult);
    } catch (e) {
      setError(String(e));
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Evaluations</h1>
        <p className="mt-1 text-sm text-zinc-400">
          Run the evaluation harness against the synthetic dataset to measure rubric scoring quality (MAE,
          correlation, evidence precision/recall).
        </p>
      </header>

      <Card className="flex items-center justify-between">
        <div>
          <div className="text-sm font-medium">Run evaluation harness</div>
          <p className="text-xs text-zinc-500">13 synthetic scenarios · consultative_sales rubric · offline mock providers</p>
        </div>
        <button
          onClick={run}
          disabled={running}
          className="rounded-xl bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-500 disabled:opacity-50"
        >
          {running ? "Running…" : "Run eval"}
        </button>
      </Card>

      {error && <EmptyState title="Evaluation failed" body={error} />}

      {result && (
        <div className="grid gap-4 sm:grid-cols-4">
          <StatCard label="Overall MAE" value={result.overall_mae.toFixed(3)} />
          <StatCard label="Correlation" value={result.overall_correlation.toFixed(3)} />
          <StatCard label="Evidence precision" value={result.evidence_precision.toFixed(3)} />
          <StatCard label="Evidence F1" value={result.evidence_f1.toFixed(3)} />
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <div className="text-xs font-medium uppercase tracking-wider text-zinc-500">{label}</div>
      <div className="mt-2 text-2xl font-semibold">{value}</div>
    </Card>
  );
}
