"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { Badge, Card, EmptyState, SectionTitle } from "@/components/ui";
import { cx, pct, scoreColor } from "@/lib/utils";

type Detail = {
  decision: string;
  confidence: number;
  summary: string;
  reason: string;
  evidence: { timestamp: string; seconds: number; quote: string; reason: string; speaker: string | null }[];
  metrics: Record<string, unknown>;
  rubric_context: { dimension: string; label: string; score: number; confidence: number }[];
  recommended_action: { type: string; message: string; urgency: string } | null;
  human_review_required: boolean;
  trace: { step: string; status: string; detail: string | null }[];
  history_context: { rep_id: string; total_calls: number; pattern_counts: Record<string, number>; last_decisions: string[]; note: string } | null;
  call_id: string | null;
  rubric_name: string | null;
  model_provider: string | null;
  report: unknown | null;
};

const TONE: Record<string, "emerald" | "amber" | "rose" | "zinc"> = { NO_ACTION: "emerald", COACH: "amber", ESCALATE: "rose" };

export default function CoachCallPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.coachCall(id).then(setDetail).catch((e) => setError(String(e)));
  }, [id]);

  if (error) return <EmptyState title="Could not load Coach decision" body={error} />;
  if (!detail) return <Card className="text-sm text-zinc-500">Loading…</Card>;

  return (
    <div className="space-y-6">
      <Link href="/coach" className="inline-flex text-sm text-zinc-400 hover:text-zinc-200">
        ← Back to Coach
      </Link>

      <Card className={cx("border-l-4", detail.decision === "ESCALATE" ? "border-l-rose-500" : detail.decision === "COACH" ? "border-l-amber-500" : "border-l-emerald-500")}>
        <div className="flex items-center gap-2">
          <Badge tone={TONE[detail.decision] ?? "zinc"}>{detail.decision}</Badge>
          <span className="font-mono text-xs text-zinc-500">{pct(detail.confidence)}</span>
          {detail.human_review_required ? <Badge tone="rose">Manager review required</Badge> : null}
        </div>
        <h1 className="mt-2 text-xl font-semibold">{detail.summary}</h1>
        <p className="mt-1 text-sm text-zinc-400">{detail.reason}</p>
        <p className="mt-2 font-mono text-xs text-zinc-600">{detail.call_id ?? id} · {detail.rubric_name ?? "consultative_sales"} · {detail.model_provider ?? "mock"}</p>
      </Card>

      {detail.recommended_action ? (
        <Card className="border-amber-900/30 bg-amber-950/10">
          <SectionTitle>Recommended action · {detail.recommended_action.urgency}</SectionTitle>
          <p className="text-sm text-zinc-200">{detail.recommended_action.message}</p>
        </Card>
      ) : null}

      {detail.evidence?.length ? (
        <Card>
          <SectionTitle>Evidence</SectionTitle>
          <div className="space-y-3">
            {detail.evidence.map((ev, i) => (
              <div key={i} className="flex gap-3 rounded-xl border border-zinc-800 bg-zinc-950/40 p-3">
                <span className="shrink-0 rounded-md bg-indigo-950 px-2 py-1 font-mono text-xs text-indigo-300">{ev.timestamp}</span>
                <div>
                  <div className="text-sm italic text-zinc-200">“{ev.quote}”</div>
                  <div className="mt-1 text-xs text-zinc-400">{ev.reason}</div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      ) : null}

      {detail.metrics ? (
        <Card>
          <SectionTitle>Metrics</SectionTitle>
          <dl className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-3">
            {Object.entries(detail.metrics).map(([k, v]) => (
              <div key={k} className="rounded-xl bg-zinc-950/60 px-3 py-2">
                <dt className="text-xs uppercase tracking-wider text-zinc-500">{k}</dt>
                <dd className="font-mono text-zinc-200">{String(v)}</dd>
              </div>
            ))}
          </dl>
        </Card>
      ) : null}

      {detail.rubric_context?.length ? (
        <Card>
          <SectionTitle>Rubric</SectionTitle>
          <div className="grid gap-2 sm:grid-cols-2">
            {detail.rubric_context.map((r) => (
              <div key={r.dimension} className="flex items-center justify-between rounded-xl border border-zinc-800 bg-zinc-950/40 px-3 py-2">
                <div>
                  <div className="text-xs font-medium text-zinc-200">{r.label}</div>
                  <div className="font-mono text-[10px] text-zinc-500">{r.dimension}</div>
                </div>
                <div className={cx("text-sm font-semibold", scoreColor(r.score))}>{r.score.toFixed(1)}</div>
              </div>
            ))}
          </div>
        </Card>
      ) : null}

      <Card>
        <SectionTitle sub="No hidden chain-of-thought — only this trace">Agent activity</SectionTitle>
        <ol className="space-y-2">
          {detail.trace.map((s, i) => (
            <li key={i} className="flex gap-3">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-emerald-950/60 text-xs text-emerald-400">✓</span>
              <div>
                <div className="text-sm font-medium text-zinc-200">{s.step}</div>
                {s.detail ? <div className="text-xs text-zinc-500">{s.detail}</div> : null}
              </div>
            </li>
          ))}
        </ol>
      </Card>
    </div>
  );
}
