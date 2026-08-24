"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { Card, EmptyState, SectionTitle } from "@/components/ui";

export default function RepsPage() {
  const [calls, setCalls] = useState<number | null>(null);

  useEffect(() => {
    api
      .listCalls()
      .then((c) => setCalls(c.length))
      .catch(() => setCalls(0));
  }, []);

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Representatives</h1>
        <p className="mt-1 text-sm text-zinc-400">
          Aggregate behavioral analytics per representative. Long-term performance is never judged from a single call.
        </p>
      </header>

      <Card>
        <SectionTitle>Demo representative</SectionTitle>
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm font-medium text-zinc-200">rep-1 · default account</div>
            <p className="text-xs text-zinc-500">{calls ?? "—"} calls uploaded in this workspace</p>
          </div>
          <Link
            href="/reps/rep-1"
            className="rounded-xl bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-500"
          >
            View analytics →
          </Link>
        </div>
      </Card>

      {calls === 0 && (
        <EmptyState
          title="No call data yet"
          body="Analyze a call first — representative analytics aggregate the rubric scores across analyzed calls."
        />
      )}
    </div>
  );
}
