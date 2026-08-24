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
};

export function formatTimestamp(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${String(m).padStart(2, "0")}:${String(r).padStart(2, "0")}`;
}
