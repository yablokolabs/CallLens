"use client";

import { use, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Rubric } from "@/lib/types";
import { Badge, Card, EmptyState } from "@/components/ui";
import { cx } from "@/lib/utils";

export default function RubricDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [rubric, setRubric] = useState<Rubric | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getRubric(id)
      .then(setRubric)
      .catch((e) => setError(String(e)));
  }, [id]);

  if (error) return <EmptyState title="Rubric not found" body={error} />;
  if (!rubric) return <Card className="text-sm text-zinc-500">Loading…</Card>;

  return (
    <div className="space-y-8">
      <header>
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight">{rubric.name}</h1>
          <Badge tone="indigo">v{rubric.version}</Badge>
        </div>
        <p className="mt-1 text-sm text-zinc-400">{rubric.description}</p>
      </header>

      <Card>
        <div className="space-y-4">
          {rubric.dimensions.map((d) => (
            <div key={d.key}>
              <div className="flex items-center justify-between text-sm">
                <span className="font-medium text-zinc-200">{d.label}</span>
                <span className="font-mono text-xs text-zinc-500">{Math.round(d.weight * 100)}% weight</span>
              </div>
              <div className="mt-1.5 h-1.5 w-full rounded-full bg-zinc-800">
                <div
                  className={cx("h-1.5 rounded-full bg-gradient-to-r from-indigo-500 to-fuchsia-500")}
                  style={{ width: `${d.weight * 100 * 6}%` }}
                />
              </div>
              <p className="mt-1 text-xs text-zinc-500">{d.description}</p>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
