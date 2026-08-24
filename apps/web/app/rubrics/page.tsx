"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { Rubric } from "@/lib/types";
import { Badge, Card, EmptyState } from "@/components/ui";

export default function RubricsPage() {
  const [rubrics, setRubrics] = useState<Rubric[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listRubrics()
      .then(setRubrics)
      .catch((e) => setError(String(e)));
  }, []);

  return (
    <div className="space-y-8">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Rubrics</h1>
          <p className="mt-1 text-sm text-zinc-400">Declarative, versioned behavioral standards.</p>
        </div>
        <Link
          href="/rubrics/new"
          className="rounded-xl bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-500"
        >
          + New rubric
        </Link>
      </header>

      {error ? (
        <EmptyState title="Cannot load rubrics" body={error} />
      ) : rubrics === null ? (
        <Card className="text-sm text-zinc-500">Loading…</Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {rubrics.map((r) => (
            <Link key={r.name} href={`/rubrics/${r.name}`}>
              <Card className="h-full transition hover:border-indigo-700/50">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-zinc-100">{r.name}</span>
                  <Badge tone="indigo">v{r.version}</Badge>
                </div>
                <p className="mt-2 line-clamp-2 text-xs text-zinc-500">{r.description || "No description"}</p>
                <div className="mt-4 flex flex-wrap gap-1.5">
                  {r.dimensions.map((d) => (
                    <span key={d.key} className="rounded-md bg-zinc-900 px-2 py-0.5 text-[10px] text-zinc-400">
                      {d.label} · {Math.round(d.weight * 100)}%
                    </span>
                  ))}
                </div>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
