"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { CallRecord } from "@/lib/types";
import { Card, EmptyState, SectionTitle, Stat } from "@/components/ui";

export default function AnalyticsPage() {
  const [calls, setCalls] = useState<CallRecord[] | null>(null);

  useEffect(() => {
    api
      .listCalls()
      .then(setCalls)
      .catch(() => setCalls([]));
  }, []);

  const statuses = (calls ?? []).reduce<Record<string, number>>((acc, c) => {
    acc[c.status] = (acc[c.status] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Analytics</h1>
        <p className="mt-1 text-sm text-zinc-400">
          Aggregate pipeline and performance telemetry for your workspace.
        </p>
      </header>

      <div className="grid gap-4 sm:grid-cols-3">
        <Stat label="Total calls" value={calls?.length ?? "—"} />
        <Stat label="Completed" value={statuses.COMPLETED ?? 0} />
        <Stat label="Failed" value={statuses.FAILED ?? 0} />
      </div>

      <Card>
        <SectionTitle>Workspace pipeline</SectionTitle>
        <p className="text-sm text-zinc-400">
          The deterministic metrics engine, multi-stage evidence extraction, and confidence gate run per call — every
          analysis records its model/prompt/rubric/pipeline versions for drift monitoring and auditability.
        </p>
        <div className="mt-4 grid gap-2 text-xs text-zinc-500">
          <div>· Metrics: talk ratio, wpm, interruptions, turns, silences — pure Python, no LLM.</div>
          <div>· Semantic: sentiment, topics, intents, opportunities, coaching — structured LLM outputs.</div>
          <div>· Scoring: candidate evidence → verification → scorer → consistency → confidence gate → bounded re-judge.</div>
          <div>· Every semantic score cites timestamped evidence you can click to replay.</div>
        </div>
      </Card>

      {calls && calls.length === 0 && (
        <EmptyState title="Nothing to chart yet" body="Upload calls to populate workspace analytics." />
      )}
    </div>
  );
}
