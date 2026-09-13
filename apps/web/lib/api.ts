import type { CallRecord, CallReport, Rubric } from "./types";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`${res.status}: ${detail.slice(0, 200)}`);
  }
  return (await res.json()) as T;
}

export const api = {
  baseUrl: BASE_URL,

  listCalls: () => request<CallRecord[]>("/api/v1/calls"),
  getCall: (id: string) => request<CallRecord>(`/api/v1/calls/${id}`),
  getAnalysis: (id: string) => request<CallReport>(`/api/v1/calls/${id}/analysis`),
  getTranscript: (id: string) => request<unknown>(`/api/v1/calls/${id}/transcript`),
  deleteCall: (id: string) => request<{ deleted: string }>(`/api/v1/calls/${id}`, { method: "DELETE" }),

  uploadCall: async (form: FormData) => {
    const res = await fetch(`${BASE_URL}/api/v1/calls`, { method: "POST", body: form });
    if (!res.ok) throw new Error(await res.text());
    return (await res.json()) as { id: string; run_id: string };
  },

  listRubrics: () => request<Rubric[]>("/api/v1/rubrics"),
  getRubric: (name: string) => request<Rubric>(`/api/v1/rubrics/${name}`),
  createRubric: (payload: unknown) => request<Rubric>("/api/v1/rubrics", { method: "POST", body: JSON.stringify(payload) }),
  validateRubric: (payload: unknown) =>
    request<{ valid: boolean; issues: string[] }>("/api/v1/rubrics/validate", { method: "POST", body: JSON.stringify(payload) }),

  repAnalytics: (repId: string) =>
    request<{
      calls_analyzed: number;
      average_score: number;
      average_confidence: number;
      dimensions: Record<string, number>;
      trend: string;
    }>(`/api/v1/reps/${repId}/analytics`),
  runEval: (payload: unknown) => request<{ overall_mae: number; runs: unknown[] }>("/api/v1/evals/run", { method: "POST", body: JSON.stringify(payload) }),

  // Coach (Strands agent — NO_ACTION / COACH / ESCALATE)
  coachSummary: () =>
    request<{
      total: number;
      by_decision: Record<string, number>;
      today_label: string;
      demo_seeded: boolean;
      seed_pending?: boolean;
      seeding?: boolean;
      seed_error?: string;
    }>("/api/coach/summary"),
  coachCalls: () =>
    request<{ id: string; call_id: string; decision: string; confidence: number; summary: string; human_review_required: boolean; created_at: string | null }[]>("/api/coach/calls"),
  coachCall: (id: string) =>
    request<{
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
      report: CallReport | null;
    }>(`/api/coach/calls/${encodeURIComponent(id)}`),
  coachRepHistory: (repId: string) =>
    request<{ rep_id: string; total_calls: number; pattern_counts: Record<string, number>; last_decisions: string[]; note: string }>(`/api/coach/reps/${encodeURIComponent(repId)}/history`),
  coachAnalyze: (body: { transcript: string; rubric_name?: string; rep_id?: string; call_id?: string }) =>
    request<{ decision: string; confidence: number; summary: string; reason: string; evidence: unknown[]; metrics: Record<string, unknown>; rubric_context: unknown[]; recommended_action: unknown | null; human_review_required: boolean; trace: unknown[]; history_context: unknown | null; call_id: string | null }>(`/api/coach/analyze`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  coachSeed: () =>
    request<{
      seeded: number;
      decisions: { call_id: string; decision: string; confidence: number }[];
      summary: { total: number; by_decision: Record<string, number> };
      seeding?: boolean;
    }>(`/api/coach/seed`, { method: "POST" }),
};

export function formatTimestamp(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${String(m).padStart(2, "0")}:${String(r).padStart(2, "0")}`;
}
