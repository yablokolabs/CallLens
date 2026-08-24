"use client";

import { api } from "@/lib/api";
import { Card, SectionTitle } from "@/components/ui";

const PROVIDERS = [
  { name: "Speech provider", value: "ElevenLabs (Scribe v2 STT)", note: "Model IDs are centralized in configuration — never scattered through logic." },
  { name: "Reasoning LLM", value: "openai / anthropic / compatible / mock", note: "Configure via LLM_PROVIDER + LLM_MODEL in the environment." },
  { name: "Storage", value: "PostgreSQL / Supabase (SQLite for local dev)", note: "Repository abstraction keeps local and production on the same API." },
  { name: "Job processing", value: "In-process async queue (MVP)", note: "Interface designed for Redis / Celery / SQS adapters." },
  { name: "Secrets", value: "Environment only", note: "API keys are never committed, logged, or exposed to the browser." },
];

const RETENTION = [
  { tier: "Audio recordings", days: 30 },
  { tier: "Transcripts", days: 90 },
  { tier: "Derived metrics & reports", days: 365 },
];

export default function SettingsPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="mt-1 text-sm text-zinc-400">
          Runtime configuration comes from the environment (see <code className="rounded bg-zinc-900 px-1 py-0.5 text-xs">.env.example</code>).
        </p>
      </header>

      <Card>
        <SectionTitle>Providers</SectionTitle>
        <div className="divide-y divide-zinc-800/60">
          {PROVIDERS.map((p) => (
            <div key={p.name} className="flex items-start justify-between gap-4 py-3">
              <div>
                <div className="text-sm font-medium text-zinc-200">{p.name}</div>
                <p className="mt-0.5 text-xs text-zinc-500">{p.note}</p>
              </div>
              <span className="shrink-0 text-xs text-zinc-400">{p.value}</span>
            </div>
          ))}
        </div>
      </Card>

      <Card>
        <SectionTitle>Privacy & retention</SectionTitle>
        <div className="divide-y divide-zinc-800/60">
          {RETENTION.map((r) => (
            <div key={r.tier} className="flex items-center justify-between py-3 text-sm">
              <span className="text-zinc-300">{r.tier}</span>
              <span className="font-mono text-xs text-zinc-500">{r.days} days</span>
            </div>
          ))}
        </div>
        <p className="mt-3 text-xs text-zinc-500">
          <code className="rounded bg-zinc-900 px-1 py-0.5">{`DELETE /api/v1/calls/{id}`}</code> removes a call and all
          associated data. Recordings use private/signed storage; transcripts are never logged by default.
        </p>
      </Card>

      <Card>
        <SectionTitle>API</SectionTitle>
        <p className="text-xs text-zinc-500">
          OpenAPI docs are served at <code className="rounded bg-zinc-900 px-1 py-0.5">{api.baseUrl}/docs</code>. The
          Python SDK ships with the package: <code className="rounded bg-zinc-900 px-1 py-0.5">from calllens import CallLens</code>.
        </p>
      </Card>
    </div>
  );
}
