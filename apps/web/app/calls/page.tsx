"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { CallRecord } from "@/lib/types";
import { Badge, Card, EmptyState, SectionTitle } from "@/components/ui";

const STATUS_TONE: Record<string, "zinc" | "emerald" | "amber" | "rose" | "indigo"> = {
  COMPLETED: "emerald",
  FAILED: "rose",
  UPLOADED: "amber",
  TRANSCRIBING: "amber",
  ANALYZING: "indigo",
};

export default function CallsPage() {
  const [calls, setCalls] = useState<CallRecord[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(() => {
    api.listCalls().then(setCalls).catch((e) => setError(String(e)));
  }, []);

  useEffect(refresh, [refresh]);

  async function onUpload(file: File, rubric: string, text: string | null) {
    setUploading(true);
    setUploadError(null);
    try {
      const form = new FormData();
      form.append("rubric", rubric);
      if (text && text.trim()) {
        form.append("transcript_source", text);
      } else {
        form.append("file", file);
      }
      await api.uploadCall(form);
      refresh();
    } catch (e) {
      setUploadError(String(e));
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Calls</h1>
        <p className="mt-1 text-sm text-zinc-400">Upload a recording or paste a transcript to analyze.</p>
      </header>

      <UploadForm onUpload={onUpload} uploading={uploading} error={uploadError} fileRef={fileRef} />

      <section>
        <SectionTitle>All calls</SectionTitle>
        {error ? (
          <EmptyState title="Cannot reach the CallLens API" body={error} />
        ) : calls === null ? (
          <Card className="text-sm text-zinc-500">Loading…</Card>
        ) : calls.length === 0 ? (
          <EmptyState title="No calls yet" body="Upload a recording or transcript above." />
        ) : (
          <div className="overflow-hidden rounded-2xl border border-zinc-800">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-zinc-800 bg-zinc-900/60 text-xs uppercase tracking-wider text-zinc-500">
                <tr>
                  <th className="px-4 py-3">Call</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Id</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/60">
                {calls.map((call) => (
                  <tr key={call.id} className="hover:bg-zinc-900/40">
                    <td className="px-4 py-3 font-medium">{call.filename ?? "transcript"}</td>
                    <td className="px-4 py-3">
                      <Badge tone={STATUS_TONE[call.status] ?? "zinc"}>{call.status}</Badge>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-zinc-500">{call.id.slice(0, 8)}</td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex justify-end gap-3 text-xs">
                        <Link href={`/calls/${call.id}`} className="text-indigo-400 hover:text-indigo-300">
                          Analysis →
                        </Link>
                        <button
                          className="text-zinc-500 hover:text-rose-400"
                          onClick={async () => {
                            await api.deleteCall(call.id);
                            refresh();
                          }}
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

function UploadForm({
  onUpload,
  uploading,
  error,
  fileRef,
}: {
  onUpload: (file: File, rubric: string, text: string | null) => void;
  uploading: boolean;
  error: string | null;
  fileRef: React.RefObject<HTMLInputElement | null>;
}) {
  const [rubric, setRubric] = useState("consultative_sales");
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);

  return (
    <Card>
      <div className="grid gap-4 md:grid-cols-2">
        <div>
          <label className="text-xs font-medium uppercase tracking-wider text-zinc-500">Recording</label>
          <input
            ref={fileRef}
            type="file"
            accept=".mp3,.wav,.m4a,.ogg,.flac,.webm,.aac,.json,.txt"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="mt-2 block w-full cursor-pointer rounded-xl border border-dashed border-zinc-700 bg-zinc-900/40 p-3 text-sm text-zinc-300 file:mr-3 file:rounded-lg file:border-0 file:bg-zinc-800 file:px-3 file:py-1.5 file:text-sm file:text-zinc-200"
          />
          <p className="mt-1 text-xs text-zinc-600">Audio (mp3/wav/m4a) or transcript (.json/.txt)</p>
        </div>
        <div>
          <label className="text-xs font-medium uppercase tracking-wider text-zinc-500">…or paste a transcript</label>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={4}
            placeholder={"00:00 REP: Hi, thanks for taking the time.\n00:10 CUSTOMER: Thanks!"}
            className="mt-2 w-full resize-none rounded-xl border border-zinc-800 bg-zinc-950 p-3 font-mono text-xs text-zinc-200 outline-none focus:border-indigo-500"
          />
        </div>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <label className="text-xs font-medium uppercase tracking-wider text-zinc-500">Rubric</label>
        <select
          value={rubric}
          onChange={(e) => setRubric(e.target.value)}
          className="rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-1.5 text-sm text-zinc-200"
        >
          <option value="consultative_sales">consultative_sales</option>
          <option value="customer_support">customer_support</option>
          <option value="recruitment">recruitment</option>
        </select>
        <button
          disabled={uploading || (!file && !text.trim())}
          onClick={() => onUpload(file ?? new File([], "transcript.txt"), rubric, text)}
          className="rounded-xl bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {uploading ? "Uploading…" : "Upload & analyze"}
        </button>
        {error ? <span className="text-xs text-rose-400">{error}</span> : null}
      </div>
    </Card>
  );
}
