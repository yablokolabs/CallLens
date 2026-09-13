"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { Badge, Card, EmptyState, SectionTitle } from "@/components/ui";
import { cx, pct, scoreColor } from "@/lib/utils";

type Summary = { total: number; by_decision: Record<string, number>; today_label: string; demo_seeded: boolean; seed_pending?: boolean; seeding?: boolean; seed_error?: string };
type CoachListItem = { id: string; call_id: string; decision: string; confidence: number; summary: string; human_review_required: boolean; created_at: string | null };
type CoachDetail = {
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

const DECISION_TONE: Record<string, "emerald" | "amber" | "rose" | "zinc"> = {
  NO_ACTION: "emerald",
  COACH: "amber",
  ESCALATE: "rose",
};

const DECISION_LABEL: Record<string, string> = {
  NO_ACTION: "No action required",
  COACH: "Coaching generated",
  ESCALATE: "Manager review required",
};

const DECISION_ICON: Record<string, string> = {
  NO_ACTION: "✓",
  COACH: "⚠",
  ESCALATE: "🔴",
};

function decisionTone(d: string) {
  return DECISION_TONE[d] ?? "zinc";
}

function prettyName(id: string): { name: string; company: string } {
  if (id === "demo-sarah-acme") return { name: "Sarah", company: "Acme Corp" };
  if (id === "demo-daniel-northstar") return { name: "Daniel", company: "Northstar" };
  if (id === "demo-maya-contoso") return { name: "Maya", company: "Contoso" };
  if (id === "demo-extra-coach-01") return { name: "Daniel", company: "Northstar (follow-up)" };
  if (id.startsWith("demo-extra-")) return { name: "Healthy", company: `Demo call ${id.slice(-2)}` };
  return { name: id.slice(0, 12), company: id };
}

export default function CoachPage() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [calls, setCalls] = useState<CoachListItem[] | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<CoachDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [seeding, setSeeding] = useState(false);
  const [filter, setFilter] = useState<"ALL" | "NO_ACTION" | "COACH" | "ESCALATE">("ALL");
  const [analyzeOpen, setAnalyzeOpen] = useState(false);
  const [analyzeTranscript, setAnalyzeTranscript] = useState("");
  const [analyzeResult, setAnalyzeResult] = useState<CoachDetail | null>(null);
  const [analyzeLoading, setAnalyzeLoading] = useState(false);

  const load = useCallback(async () => {
    try {
      const [s, c] = await Promise.all([api.coachSummary(), api.coachCalls()]);
      setSummary(s);
      // Sort: ESCALATE first, COACH next, NO_ACTION last, then by id
      const order: Record<string, number> = { ESCALATE: 0, COACH: 1, NO_ACTION: 2 };
      c.sort((a, b) => (order[a.decision] ?? 9) - (order[b.decision] ?? 9) || (a.call_id ?? "").localeCompare(b.call_id ?? ""));
      setCalls(c);
      setError(null);
    } catch (e) {
      setError(String(e));
    }
  }, []);

  useEffect(() => {
    // data fetch on mount — setState in fetch callback is intentional
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  useEffect(() => {
    // derive initial selection from fetched calls — not cascading derived state
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (calls && calls.length && !selectedId) setSelectedId(calls[0].call_id);
  }, [calls, selectedId]);

  useEffect(() => {
    if (!selectedId) return;
    api
      .coachCall(selectedId)
      .then(setDetail)
      .catch(() => setDetail(null));
  }, [selectedId]);

  const handleSeed = async () => {
    setSeeding(true);
    try {
      const res = await api.coachSeed();
      if ((res as unknown as { seeding?: boolean }).seeding) {
        // Live provider — seeds 18 Sarvam calls in background (~90s). Poll until done.
        for (let i = 0; i < 45; i++) {
          await new Promise((r) => setTimeout(r, 2000));
          const [s, c] = await Promise.all([api.coachSummary(), api.coachCalls()]);
          setSummary(s);
          const order: Record<string, number> = { ESCALATE: 0, COACH: 1, NO_ACTION: 2 };
          c.sort((a, b) => (order[a.decision] ?? 9) - (order[b.decision] ?? 9) || (a.call_id ?? "").localeCompare(b.call_id ?? ""));
          setCalls(c);
          if ((s as Summary).total > 0) break;
          if ((s as Summary).seed_error) {
            setError(`Seed failed: ${(s as Summary).seed_error}`);
            break;
          }
        }
      } else {
        await load();
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setSeeding(false);
    }
  };

  const handleAnalyze = async () => {
    if (!analyzeTranscript.trim()) return;
    setAnalyzeLoading(true);
    try {
      const res = await api.coachAnalyze({ transcript: analyzeTranscript, rubric_name: "consultative_sales" });
      // Map analyze response to CoachDetail shape
      setAnalyzeResult(res as unknown as CoachDetail);
      await load();
    } catch (e) {
      setError(String(e));
    } finally {
      setAnalyzeLoading(false);
    }
  };

  const by = summary?.by_decision ?? { NO_ACTION: 0, COACH: 0, ESCALATE: 0 };
  const visibleCalls = (calls ?? []).filter((c) => filter === "ALL" || c.decision === filter);

  // Feature call order for hero demo section (the 3 deterministc ones first)
  const heroOrder = ["demo-sarah-acme", "demo-daniel-northstar", "demo-maya-contoso", "demo-extra-coach-01"];
  const heroCalls = heroOrder.map((id) => (calls ?? []).find((c) => c.call_id === id)).filter(Boolean) as CoachListItem[];
  const otherCalls = (calls ?? []).filter((c) => !heroOrder.includes(c.call_id ?? ""));

  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-indigo-800/50 bg-indigo-950/30 px-3 py-1 text-[11px] font-medium uppercase tracking-widest text-indigo-300">
            <span className="h-1.5 w-1.5 rounded-full bg-indigo-400" />
            Strands Agents SDK · MCP · agentic-ai
          </div>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight">CALLLENS COACH</h1>
          <p className="mt-1 text-sm text-zinc-400">The autonomous manager — reviews every call, acts only when it should.</p>
          <p className="mt-1 text-[11px] font-medium uppercase tracking-widest text-indigo-400/80">Decision engine: Strands Agents SDK — CallLens is the evidence layer</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleSeed}
            disabled={seeding}
            className="rounded-xl bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-500 disabled:opacity-50"
          >
            {seeding ? "Seeding live calls…" : "Load Demo Calls"}
          </button>
          {seeding ? <span className="text-xs text-zinc-500">Live Sarvam — ~60–90s for 18 calls, page stays responsive</span> : null}
          <a
            href={`${api.baseUrl}/docs`}
            target="_blank"
            rel="noreferrer"
            className="rounded-xl border border-zinc-800 bg-zinc-900 px-4 py-2 text-sm text-zinc-300 hover:bg-zinc-800"
          >
            API docs →
          </a>
        </div>
      </header>

      {error ? (
        <Card className="border-rose-900/40 bg-rose-950/20">
          <div className="text-sm font-medium text-rose-300">Cannot reach the Coach API</div>
          <p className="mt-1 text-xs text-zinc-400">{error}. Start the backend: <code className="rounded bg-zinc-900 px-1 py-0.5">docker compose up</code> or <code className="rounded bg-zinc-900 px-1 py-0.5">DEMO_MODE=true</code></p>
          <button onClick={load} className="mt-3 rounded-lg border border-zinc-700 px-3 py-1.5 text-xs text-zinc-300 hover:bg-zinc-900">
            Retry
          </button>
        </Card>
      ) : null}

      {/* TODAY summary — the judge screenshot target */}
      <section>
        <div className="flex items-baseline justify-between">
          <SectionTitle sub="Autonomous review — silence is a correct outcome">Today</SectionTitle>
          <span className="text-xs text-zinc-500">{summary ? `${summary.total} calls analyzed` : "—"} · Decision engine: Strands Agents SDK</span>
        </div>
        <div className="grid gap-4 sm:grid-cols-3">
          <Card className="border-emerald-900/30 bg-emerald-950/10">
            <div className="text-xs font-medium uppercase tracking-wider text-zinc-500">No action required</div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-3xl font-bold text-emerald-400">{by.NO_ACTION ?? 0}</span>
              <span className="text-sm text-zinc-500">✓ silent</span>
            </div>
            <div className="mt-1 text-xs text-zinc-500">Healthy conversations — no interruption warranted.</div>
          </Card>
          <Card className="border-amber-900/30 bg-amber-950/10">
            <div className="text-xs font-medium uppercase tracking-wider text-zinc-500">Coaching generated</div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-3xl font-bold text-amber-400">{by.COACH ?? 0}</span>
              <span className="text-sm text-zinc-500">⚠ evidence-backed</span>
            </div>
            <div className="mt-1 text-xs text-zinc-500">Targeted tip with timestamp + metric + rubric.</div>
          </Card>
          <Card className="border-rose-900/30 bg-rose-950/20">
            <div className="text-xs font-medium uppercase tracking-wider text-zinc-500">Manager review required</div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-3xl font-bold text-rose-400">{by.ESCALATE ?? 0}</span>
              <span className="text-sm text-zinc-500">🔴 human-in-the-loop</span>
            </div>
            <div className="mt-1 text-xs text-zinc-500">Churn / risk / compliance — human judgment needed.</div>
          </Card>
        </div>
        <div className="mt-3 flex flex-wrap gap-2 text-xs">
          {(["ALL", "NO_ACTION", "COACH", "ESCALATE"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={cx(
                "rounded-full border px-3 py-1 font-medium transition",
                filter === f ? "border-indigo-600 bg-indigo-600 text-white" : "border-zinc-800 bg-zinc-900 text-zinc-400 hover:bg-zinc-800"
              )}
            >
              {f === "ALL" ? `All (${summary?.total ?? 0})` : `${DECISION_LABEL[f]} (${by[f] ?? 0})`}
            </button>
          ))}
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-[380px_1fr]">
        {/* Call list */}
        <div className="space-y-3">
          <SectionTitle sub="Tap a call to inspect — View evidence opens the detail panel">Recent calls</SectionTitle>
          {calls === null ? (
            <Card className="text-sm text-zinc-500">Loading…</Card>
          ) : visibleCalls.length === 0 ? (
            <EmptyState title="No calls match this filter" body="Switch to All or seed demo calls." />
          ) : (
            <div className="space-y-2">
              {/* Hero 3 + follow-up first */}
              {filter === "ALL" && heroCalls.length > 0 ? (
                <div className="space-y-2">
                  {heroCalls.map((call) => {
                    const { name, company } = prettyName(call.call_id);
                    const active = selectedId === call.call_id;
                    return (
                      <button
                        key={call.call_id}
                        onClick={() => setSelectedId(call.call_id)}
                        className={cx(
                          "w-full rounded-2xl border p-4 text-left transition",
                          active ? "border-indigo-600 bg-indigo-950/20" : "border-zinc-800 bg-zinc-900/40 hover:bg-zinc-900"
                        )}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0">
                            <div className="text-sm font-medium">
                              {name} — {company}
                            </div>
                            <div className="mt-1 flex items-center gap-2">
                              <Badge tone={decisionTone(call.decision)}>
                                {DECISION_ICON[call.decision]} {DECISION_LABEL[call.decision] ?? call.decision}
                              </Badge>
                              <span className="font-mono text-[10px] text-zinc-500">{pct(call.confidence)}</span>
                            </div>
                          </div>
                          <span className="shrink-0 text-xs text-indigo-400">View evidence →</span>
                        </div>
                        <div className="mt-2 line-clamp-2 text-xs text-zinc-400">{call.summary}</div>
                        {call.human_review_required ? (
                          <div className="mt-2 inline-flex rounded-full bg-rose-950/50 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-rose-300">
                            Manager review required
                          </div>
                        ) : null}
                      </button>
                    );
                  })}
                  <div className="py-1 text-[10px] font-semibold uppercase tracking-widest text-zinc-600">More calls</div>
                </div>
              ) : null}
              {(filter === "ALL" ? otherCalls.filter((c) => filter === "ALL" || c.decision === filter) : visibleCalls).slice(0, 20).map((call) => {
                // When hero section rendered, visibleCalls already split — avoid duplicating hero in the \"others\" on ALL
                if (filter === "ALL" && heroOrder.includes(call.call_id)) return null;
                const { name, company } = prettyName(call.call_id);
                const active = selectedId === call.call_id;
                return (
                  <button
                    key={call.call_id}
                    onClick={() => setSelectedId(call.call_id)}
                    className={cx(
                      "w-full rounded-2xl border p-4 text-left transition",
                      active ? "border-indigo-600 bg-indigo-950/20" : "border-zinc-800 bg-zinc-900/40 hover:bg-zinc-900"
                    )}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <div className="truncate text-sm font-medium">
                          {name} — {company}
                        </div>
                        <div className="mt-1 flex items-center gap-2">
                          <Badge tone={decisionTone(call.decision)}>
                            {DECISION_ICON[call.decision]} {DECISION_LABEL[call.decision] ?? call.decision}
                          </Badge>
                          <span className="font-mono text-[10px] text-zinc-500">{pct(call.confidence)}</span>
                        </div>
                      </div>
                      <span className="shrink-0 text-xs text-indigo-400">View →</span>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
          <div className="flex gap-2 pt-2">
            <Link href="/dashboard" className="text-xs text-zinc-500 hover:text-zinc-300">
              ← Classic dashboard
            </Link>
            <span className="text-xs text-zinc-700">·</span>
            <Link href="/calls" className="text-xs text-zinc-500 hover:text-zinc-300">
              Upload a transcript
            </Link>
          </div>
        </div>

        {/* Evidence + trace panel — the main hackathon screenshot */}
        <div className="space-y-4">
          {!selectedId || !detail ? (
            <Card className="py-12 text-center">
              <div className="text-sm font-medium text-zinc-300">Select a call</div>
              <p className="mx-auto mt-1 max-w-md text-xs text-zinc-500">Choose one of the three demo calls on the left. Sarah → NO_ACTION, Daniel → COACH, Maya → ESCALATE. Each shows why the agent acted.</p>
            </Card>
          ) : (
            <>
              {/* Decision header */}
              <Card
                className={cx(
                  "border-l-4",
                  detail.decision === "ESCALATE"
                    ? "border-l-rose-500 bg-rose-950/10"
                    : detail.decision === "COACH"
                      ? "border-l-amber-500 bg-amber-950/10"
                      : "border-l-emerald-500 bg-emerald-950/10"
                )}
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <Badge tone={decisionTone(detail.decision)}>{DECISION_ICON[detail.decision]} {detail.decision}</Badge>
                      <span className="font-mono text-xs text-zinc-500">{pct(detail.confidence)} confidence</span>
                      {detail.model_provider ? <span className="rounded-full border border-zinc-800 bg-zinc-900 px-2 py-0.5 font-mono text-[10px] text-zinc-500">{detail.model_provider}</span> : null}
                    </div>
                    <h2 className="mt-2 text-lg font-semibold leading-tight">{detail.summary}</h2>
                    <p className="mt-1 text-sm text-zinc-400">{detail.reason}</p>
                    {detail.human_review_required ? (
                      <div className="mt-3 inline-flex items-center gap-2 rounded-xl bg-rose-950/60 px-3 py-2 text-sm font-medium text-rose-200">
                        <span>🔴</span> Manager review required — human-in-the-loop
                      </div>
                    ) : null}
                  </div>
                  <Link
                    href={`/coach/${encodeURIComponent(detail.call_id ?? selectedId)}`}
                    className="shrink-0 rounded-xl border border-zinc-800 bg-zinc-950 px-3 py-1.5 text-xs text-zinc-300 hover:bg-zinc-900"
                  >
                    Full page →
                  </Link>
                </div>

                {/* Key metrics — explainable-ai */}
                <div className="mt-4 grid grid-cols-2 gap-3 border-t border-zinc-800/60 pt-4 sm:grid-cols-4">
                  {[
                    ["Talk ratio", detail.metrics?.rep_talk_ratio != null ? pct(Number(detail.metrics.rep_talk_ratio)) : "—", "rep share"],
                    ["Overall", detail.metrics?.overall_score != null ? `${Number(detail.metrics.overall_score).toFixed(0)}/100` : "—", "call score"],
                    ["Worst dim", detail.metrics?.worst_dimension ? String(detail.metrics.worst_dimension) : "—", detail.metrics?.worst_score != null ? `${Number(detail.metrics.worst_score).toFixed(1)}/10` : ""],
                    ["Questions", detail.metrics?.open_questions != null ? String(detail.metrics.open_questions) : "—", "open Qs"],
                  ].map(([label, value, sub]) => (
                    <div key={label} className="rounded-xl bg-zinc-950/60 p-3 text-center">
                      <div className="text-xs uppercase tracking-wider text-zinc-500">{label}</div>
                      <div className="mt-1 text-lg font-semibold">{value as string}</div>
                      <div className="text-[10px] text-zinc-600">{sub as string}</div>
                    </div>
                  ))}
                </div>

                {/* Rubric strip */}
                {detail.rubric_context?.length ? (
                  <div className="mt-4">
                    <div className="text-[11px] font-semibold uppercase tracking-wider text-zinc-500">Rubric</div>
                    <div className="mt-2 grid gap-2 sm:grid-cols-2">
                      {detail.rubric_context.slice(0, 4).map((r) => (
                        <div key={r.dimension} className="flex items-center justify-between rounded-xl border border-zinc-800 bg-zinc-950/40 px-3 py-2">
                          <div>
                            <div className="text-xs font-medium text-zinc-200">{r.label}</div>
                            <div className="font-mono text-[10px] text-zinc-500">{r.dimension}</div>
                          </div>
                          <div className="text-right">
                            <div className={cx("text-sm font-semibold", scoreColor(r.score))}>{r.score.toFixed(1)}</div>
                            <div className="font-mono text-[10px] text-zinc-500">{pct(r.confidence)}</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}
              </Card>

              {/* Evidence panel */}
              {detail.evidence?.length ? (
                <Card>
                  <SectionTitle sub="Timestamps are the receipts — every coaching claim points to a moment">Evidence</SectionTitle>
                  <div className="space-y-3">
                    {detail.evidence.map((ev, i) => (
                      <div key={i} className="flex gap-3 rounded-xl border border-zinc-800 bg-zinc-950/40 p-3">
                        <span className="shrink-0 rounded-md bg-indigo-950 px-2 py-1 font-mono text-xs text-indigo-300">{ev.timestamp}</span>
                        <div className="min-w-0">
                          <div className="text-sm italic text-zinc-200">“{ev.quote}”</div>
                          <div className="mt-1 text-xs text-zinc-400">{ev.reason}</div>
                          {ev.speaker ? <div className="mt-1 font-mono text-[10px] text-zinc-600">{ev.speaker}</div> : null}
                        </div>
                      </div>
                    ))}
                  </div>
                </Card>
              ) : (
                <Card>
                  <div className="text-sm font-medium text-zinc-300">No evidence needed</div>
                  <p className="mt-1 text-xs text-zinc-500">This call is healthy — the correct autonomous behavior is silence. No coaching or escalation is warranted.</p>
                </Card>
              )}

              {/* Recommended action */}
              {detail.recommended_action ? (
                <Card className={detail.decision === "ESCALATE" ? "border-rose-900/40 bg-rose-950/10" : "border-amber-900/30 bg-amber-950/10"}>
                  <div className="flex items-start gap-3">
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-zinc-950 text-sm">
                      {detail.decision === "ESCALATE" ? "🔴" : "✦"}
                    </div>
                    <div className="min-w-0">
                      <div className="text-xs font-semibold uppercase tracking-wider text-zinc-400">Recommended action · {detail.recommended_action.urgency}</div>
                      <p className="mt-1 text-sm font-medium text-zinc-100">{detail.recommended_action.message}</p>
                      {detail.decision === "ESCALATE" ? (
                        <p className="mt-2 text-xs text-zinc-400">The agent escalated — a human manager should review this conversation.</p>
                      ) : (
                        <p className="mt-2 text-xs text-zinc-400">Evidence-backed coaching — cites a timestamp and a metric.</p>
                      )}
                    </div>
                  </div>
                </Card>
              ) : null}

              {/* Agent activity trace — no hidden chain-of-thought */}
              <Card>
                <SectionTitle sub="What the agent did — not what it thought">Agent activity</SectionTitle>
                <div className="mb-3 flex flex-wrap items-center gap-1.5">
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">Decision engine:</span>
                  <span className="rounded-full border border-indigo-900/40 bg-indigo-950/30 px-2 py-0.5 text-[10px] font-medium text-indigo-300">Strands Agents SDK</span>
                  <span className="text-[10px] text-zinc-600">· CallLens is the evidence layer</span>
                </div>
                {detail.trace.some((s) => s.step.includes("Strands requested")) ? (
                  <div className="mb-3 rounded-xl border border-zinc-800 bg-zinc-950/40 px-3 py-2">
                    <div className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">Agent tools used</div>
                    <div className="mt-1 flex flex-wrap gap-1.5">
                      {detail.trace
                        .filter((s) => s.step.includes("Strands requested"))
                        .map((s) => s.step.replace("Strands requested ", ""))
                        .map((tool) => (
                          <span key={tool} className="rounded-full border border-zinc-800 bg-zinc-900 px-2 py-0.5 font-mono text-[10px] text-zinc-300">
                            {tool}
                          </span>
                        ))}
                    </div>
                  </div>
                ) : null}
                <ol className="space-y-2">
                  {detail.trace.map((step, i) => (
                    <li key={i} className="flex gap-3">
                      <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-emerald-950/60 text-[11px] text-emerald-400">✓</span>
                      <div className="min-w-0">
                        <div className="text-sm font-medium text-zinc-200">{step.step}</div>
                        {step.detail ? <div className="text-xs text-zinc-500">{step.detail}</div> : null}
                      </div>
                    </li>
                  ))}
                </ol>
                {detail.history_context ? (
                  <div className="mt-4 rounded-xl border border-zinc-800 bg-zinc-950/40 p-3">
                    <div className="text-xs font-semibold uppercase tracking-wider text-zinc-500">Rep history · 5-call window</div>
                    <div className="mt-1 text-xs text-zinc-400">{detail.history_context.note}</div>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {Object.entries(detail.history_context.pattern_counts).map(([k, v]) => (
                        <span key={k} className="rounded-full border border-zinc-800 bg-zinc-900 px-2 py-0.5 font-mono text-[10px] text-zinc-400">
                          {k} {v}/{detail.history_context!.total_calls}
                        </span>
                      ))}
                    </div>
                    {detail.history_context.last_decisions?.length ? (
                      <div className="mt-2 flex gap-1.5">
                        {detail.history_context.last_decisions.map((d, i) => (
                          <Badge key={i} tone={decisionTone(d) as never}>{d}</Badge>
                        ))}
                      </div>
                    ) : null}
                  </div>
                ) : null}
              </Card>
            </>
          )}
        </div>
      </div>

      {/* Analyze a transcript — sales-coaching / conversation-intelligence in action */}
      <section>
        <button
          onClick={() => setAnalyzeOpen(!analyzeOpen)}
          className="flex w-full items-center justify-between rounded-2xl border border-zinc-800 bg-zinc-900/40 px-4 py-3 text-left hover:bg-zinc-900"
        >
          <div>
            <div className="text-sm font-medium">Analyze a transcript</div>
            <div className="text-xs text-zinc-500">Paste any call — the Strands agent will decide NO_ACTION · COACH · ESCALATE with evidence.</div>
          </div>
          <span className="text-zinc-500">{analyzeOpen ? "−" : "+"}</span>
        </button>
        {analyzeOpen ? (
          <Card className="mt-3">
            <textarea
              value={analyzeTranscript}
              onChange={(e) => setAnalyzeTranscript(e.target.value)}
              placeholder={"00:00 REP: Hi — how is onboarding?\n00:12 CUSTOMER: ...\n..."}
              rows={8}
              className="w-full rounded-xl border border-zinc-800 bg-zinc-950 p-3 font-mono text-xs text-zinc-200 placeholder:text-zinc-600 focus:border-indigo-600 focus:outline-none"
            />
            <div className="mt-3 flex items-center gap-2">
              <button
                onClick={handleAnalyze}
                disabled={analyzeLoading || !analyzeTranscript.trim()}
                className="rounded-xl bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
              >
                {analyzeLoading ? "Analyzing…" : "Analyze"}
              </button>
              <span className="text-xs text-zinc-500">Uses mock LLM when no keys are set — no paid calls.</span>
            </div>
            {analyzeResult ? (
              <div className="mt-4 rounded-xl border border-zinc-800 bg-zinc-950/60 p-4">
                <div className="flex items-center gap-2">
                  <Badge tone={decisionTone(analyzeResult.decision)}>{analyzeResult.decision}</Badge>
                  <span className="font-mono text-xs text-zinc-500">{pct(analyzeResult.confidence)}</span>
                  {analyzeResult.human_review_required ? <Badge tone="rose">human review required</Badge> : null}
                </div>
                <p className="mt-2 text-sm text-zinc-200">{analyzeResult.summary}</p>
                <p className="mt-1 text-xs text-zinc-500">{analyzeResult.reason}</p>
                {analyzeResult.evidence?.length ? (
                  <ul className="mt-3 space-y-2">
                    {analyzeResult.evidence.map((ev, i) => (
                      <li key={i} className="flex gap-2 text-xs">
                        <span className="shrink-0 rounded bg-indigo-950 px-1.5 py-0.5 font-mono text-indigo-300">{ev.timestamp}</span>
                        <span className="text-zinc-400">“{ev.quote}” — {ev.reason}</span>
                      </li>
                    ))}
                  </ul>
                ) : null}
                {analyzeResult.recommended_action ? (
                  <p className="mt-3 rounded-lg bg-amber-950/20 px-3 py-2 text-sm text-amber-200">{analyzeResult.recommended_action.message}</p>
                ) : null}
              </div>
            ) : null}
          </Card>
        ) : null}
      </section>

      <div className="rounded-2xl border border-zinc-800 bg-zinc-900/30 p-4 text-xs leading-relaxed text-zinc-500">
        <span className="font-medium text-zinc-300">Strands is the decision layer, CallLens is the evidence layer.</span> CallLens (LangGraph + rubric engine) produces timestamped, verified scoring. The Strands Coach Agent consumes it via tools/MCP, consults rep history, and makes the explainable NO_ACTION / COACH / ESCALATE call — with human-in-the-loop only on ESCALATE. The <Link href="/calls" className="text-indigo-400 hover:text-indigo-300">classic CallLens view</Link> stays available unchanged.
      </div>
    </div>
  );
}
