"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Card, SectionTitle } from "@/components/ui";

interface DimRow {
  key: string;
  label: string;
  weight: string;
  description: string;
}

export default function NewRubricPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [version, setVersion] = useState("1.0");
  const [description, setDescription] = useState("");
  const [dims, setDims] = useState<DimRow[]>([{ key: "", label: "", weight: "1.0", description: "" }]);
  const [issues, setIssues] = useState<string[]>([]);

  async function create() {
    const payload = {
      name,
      version,
      description,
      dimensions: Object.fromEntries(
        dims
          .filter((d) => d.key.trim())
          .map((d) => [d.key.trim(), { label: d.label.trim() || d.key.trim(), weight: parseFloat(d.weight), description: d.description }])
      ),
    };
    const validation = await api.validateRubric(payload);
    if (!validation.valid) {
      setIssues(validation.issues);
      return;
    }
    setIssues([]);
    await api.createRubric(payload);
    router.push(`/rubrics/${name}`);
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">New rubric</h1>
        <p className="mt-1 text-sm text-zinc-400">
          Rubrics are declarative and versioned. Dimension weights must sum to 1.0.
        </p>
      </header>

      <Card className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="rubric name (e.g. customer_success)"
            className="rounded-xl border border-zinc-800 bg-zinc-950 px-3 py-2 text-sm outline-none focus:border-indigo-500"
          />
          <input
            value={version}
            onChange={(e) => setVersion(e.target.value)}
            placeholder="version (e.g. 1.0)"
            className="rounded-xl border border-zinc-800 bg-zinc-950 px-3 py-2 text-sm outline-none focus:border-indigo-500"
          />
        </div>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Short description of what this rubric evaluates"
          className="w-full resize-none rounded-xl border border-zinc-800 bg-zinc-950 px-3 py-2 text-sm outline-none focus:border-indigo-500"
          rows={2}
        />

        <SectionTitle>Dimensions</SectionTitle>
        <div className="space-y-3">
          {dims.map((d, i) => (
            <div key={i} className="grid grid-cols-[1fr_1fr_5rem_2rem] gap-2">
              <input
                value={d.key}
                onChange={(e) => setDims(dims.map((x, j) => (j === i ? { ...x, key: e.target.value } : x)))}
                placeholder="key (e.g. empathy)"
                className="rounded-lg border border-zinc-800 bg-zinc-950 px-2 py-1.5 font-mono text-xs outline-none focus:border-indigo-500"
              />
              <input
                value={d.label}
                onChange={(e) => setDims(dims.map((x, j) => (j === i ? { ...x, label: e.target.value } : x)))}
                placeholder="Label"
                className="rounded-lg border border-zinc-800 bg-zinc-950 px-2 py-1.5 text-xs outline-none focus:border-indigo-500"
              />
              <input
                value={d.weight}
                onChange={(e) => setDims(dims.map((x, j) => (j === i ? { ...x, weight: e.target.value } : x)))}
                placeholder="0.5"
                className="rounded-lg border border-zinc-800 bg-zinc-950 px-2 py-1.5 font-mono text-xs outline-none focus:border-indigo-500"
              />
              <button
                onClick={() => setDims(dims.filter((_, j) => j !== i))}
                className="text-zinc-600 hover:text-rose-400"
                title="Remove"
              >
                ✕
              </button>
            </div>
          ))}
          <button
            onClick={() => setDims([...dims, { key: "", label: "", weight: "", description: "" }])}
            className="text-xs text-indigo-400 hover:text-indigo-300"
          >
            + Add dimension
          </button>
        </div>

        {issues.length > 0 && (
          <ul className="rounded-xl border border-rose-800/40 bg-rose-950/20 p-3 text-xs text-rose-300">
            {issues.map((i, j) => (
              <li key={j}>{i}</li>
            ))}
          </ul>
        )}

        <button
          onClick={create}
          className="w-full rounded-xl bg-indigo-600 py-2 text-sm font-medium text-white transition hover:bg-indigo-500"
        >
          Create rubric
        </button>
      </Card>
    </div>
  );
}
