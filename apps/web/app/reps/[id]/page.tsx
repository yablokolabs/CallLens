"use client";

import { use, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Badge, Card, EmptyState, SectionTitle, Stat } from "@/components/ui";
import { cx } from "@/lib/utils";

interface RepAnalytics {
  calls_analyzed: number;
  average_score: number;
  average_confidence: number;
  dimensions: Record<string, number>;
  trend: string;
}

export default function RepDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [data, setData] = useState<RepAnalytics | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .repAnalytics(id)
      .then(setData)
      .catch((e) => setError(String(e)));
  }, [id]);

  if (error) return <EmptyState title="No analytics" body={error} />;
  if (!data) return <Card className="text-sm text-zinc-500">Loading…</Card>;

  const dims = Object.entries(data.dimensions).sort((a, b) => b[1] - a[1]);

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Representative · {id}</h1>
        <p className="mt-1 text-sm text-zinc-400">{data.trend}</p>
      </header>

      <div className="grid gap-4 sm:grid-cols-3">
        <Stat label="Average score" value={data.average_score.toFixed(1)} />
        <Stat label="Calls analyzed" value={data.calls_analyzed} />
        <Stat label="Avg confidence" value={`${(data.average_confidence * 100).toFixed(0)}%`} />
      </div>

      {dims.length === 0 ? (
        <EmptyState
          title="No scored dimensions yet"
          body="Analyze at least one call for this workspace to see per-dimension averages."
        />
      ) : (
        <Card>
          <SectionTitle>Dimension averages</SectionTitle>
          <div className="space-y-3">
            {dims.map(([dim, score]) => (
              <div key={dim} className="flex items-center gap-3">
                <span className="w-48 shrink-0 truncate text-sm text-zinc-300">{dim}</span>
                <div className="h-2 flex-1 rounded-full bg-zinc-800">
                  <div
                    className={cx("h-2 rounded-full", score >= 8 ? "bg-emerald-500" : score >= 6 ? "bg-amber-500" : "bg-rose-500")}
                    style={{ width: `${score * 10}%` }}
                  />
                </div>
                <span className="w-10 text-right font-mono text-sm">{score.toFixed(1)}</span>
              </div>
            ))}
          </div>
        </Card>
      )}

      <div>
        <Badge tone="zinc">Trends (↑ / ↓ over 30 days) appear once calls are linked to representatives in production.</Badge>
      </div>
    </div>
  );
}
