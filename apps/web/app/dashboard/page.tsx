"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, formatTimestamp } from "@/lib/api";
import type { CallRecord } from "@/lib/types";
import { Badge, Card, EmptyState, SectionTitle, Stat } from "@/components/ui";
import { cx } from "@/lib/utils";

const STATUS_TONE: Record<string, "zinc" | "emerald" | "amber" | "rose"> = {
  COMPLETED: "emerald",
  FAILED: "rose",
  UPLOADED: "amber",
  TRANSCRIBING: "amber",
  ANALYZING: "indigo" as never,
};

export default function DashboardPage() {
  const [calls, setCalls] = useState<CallRecord[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listCalls()
      .then(setCalls)
      .catch((e) => setError(String(e)));
  }, []);

  const completed = (calls ?? []).filter((c) => c.status === "COMPLETED").length;

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <p className="mt-1 text-sm text-zinc-400">
          Evidence-backed conversation intelligence for your team.
        </p>
      </header>

      <div className="grid gap-4 sm:grid-cols-3">
        <Stat label="Calls uploaded" value={calls?.length ?? "—"} />
        <Stat label="Analyzed" value={completed} />
        <Stat label="API" value={<span className="font-mono text-sm">{api.baseUrl.replace("http://", "")}</span>} />
      </div>

      <section>
        <SectionTitle>Recent calls</SectionTitle>
        {error ? (
          <EmptyState title="Cannot reach the CallLens API" body={`${error}. Start the backend with: calllens server (or docker compose up).`} />
        ) : calls === null ? (
          <Card className="text-sm text-zinc-500">Loading…</Card>
        ) : calls.length === 0 ? (
          <EmptyState title="No calls yet" body="Upload a recording or transcript from the Calls page to get started." />
        ) : (
          <div className="overflow-hidden rounded-2xl border border-zinc-800">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-zinc-800 bg-zinc-900/60 text-xs uppercase tracking-wider text-zinc-500">
                <tr>
                  <th className="px-4 py-3">Call</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Id</th>
                  <th className="px-4 py-3 text-right">Open</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/60">
                {calls.slice(0, 8).map((call) => (
                  <tr key={call.id} className="hover:bg-zinc-900/40">
                    <td className="px-4 py-3 font-medium">{call.filename ?? "transcript"}</td>
                    <td className="px-4 py-3">
                      <Badge tone={STATUS_TONE[call.status] ?? "zinc"}>{call.status}</Badge>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-zinc-500">{call.id.slice(0, 8)}</td>
                    <td className="px-4 py-3 text-right">
                      <Link href={`/calls/${call.id}`} className={cx("text-indigo-400 hover:text-indigo-300")}>
                        Open →
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section>
        <SectionTitle>Upload a call</SectionTitle>
        <Link
          href="/calls"
          className="inline-flex rounded-xl bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-500"
        >
          Go to Calls
        </Link>
        <p className="mt-3 text-xs text-zinc-500">
          Tip: {formatTimestamp(0)} timestamps in the report are clickable — they seek the audio player.
        </p>
      </section>
    </div>
  );
}
