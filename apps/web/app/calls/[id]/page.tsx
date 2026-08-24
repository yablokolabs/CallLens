"use client";

import { use, useEffect, useRef, useState } from "react";
import { api, formatTimestamp } from "@/lib/api";
import type { CallReport, Evidence, RubricScore, Transcript as TranscriptModel } from "@/lib/types";
import { Badge, Card, EmptyState, SectionTitle } from "@/components/ui";
import { confidenceColor, cx, pct, scoreColor } from "@/lib/utils";

export default function CallDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [report, setReport] = useState<CallReport | null>(null);
  const [transcript, setTranscript] = useState<TranscriptModel | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [seekTo, setSeekTo] = useState<number | null>(null);
  const audioRef = useRef<HTMLAudioElement>(null);

  useEffect(() => {
    Promise.all([api.getAnalysis(id), api.getTranscript(id).catch(() => null)])
      .then(([r, t]) => {
        setReport(r);
        setTranscript(t as TranscriptModel | null);
      })
      .catch((e) => setError(String(e)));
  }, [id]);

  useEffect(() => {
    if (seekTo !== null && audioRef.current) {
      audioRef.current.currentTime = seekTo;
      audioRef.current.play().catch(() => undefined);
    }
  }, [seekTo]);

  if (error) return <EmptyState title="Could not load analysis" body={error} />;
  if (!report) return <Card className="text-sm text-zinc-500">Loading analysis…</Card>;

  const metrics = report.metrics;

  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Customer ↔ Representative</h1>
          <p className="mt-1 font-mono text-xs text-zinc-500">{report.call_id}</p>
          {metrics ? <p className="mt-1 text-sm text-zinc-400">{formatTimestamp(metrics.duration)} · {metrics.turns} turns</p> : null}
        </div>
        <div className="flex items-center gap-4">
          <div className="text-center">
            <div className={cx("text-4xl font-bold", scoreColor(report.overall_score / 10))}>
              {Math.round(report.overall_score)}
            </div>
            <div className="text-xs uppercase tracking-wider text-zinc-500">Overall /100</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-semibold text-zinc-200">{pct(report.confidence)}</div>
            <div className="text-xs uppercase tracking-wider text-zinc-500">Confidence</div>
          </div>
          <Badge tone="emerald">{report.sentiment?.customer?.overall ?? "—"} customer</Badge>
        </div>
      </header>

      {metrics && <AudioPanel duration={metrics.duration} audioRef={audioRef} />}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <SectionTitle>Behavioral Rubric</SectionTitle>
          <div className="space-y-4">
            {report.rubric_scores.map((score) => (
              <RubricScoreRow key={score.dimension} score={score} onSeek={setSeekTo} />
            ))}
          </div>
        </Card>

        <div className="space-y-6">
          {metrics && <TalkRatioCard metrics={report.metrics!} />}
          {report.sentiment && <SentimentCard report={report} />}
        </div>
      </div>

      {report.topics.length > 0 && (
        <Card>
          <SectionTitle>Topics</SectionTitle>
          <div className="flex flex-wrap gap-2">
            {report.topics.map((t, i) => (
              <button
                key={i}
                onClick={() => setSeekTo(t.start_time)}
                className="rounded-full border border-zinc-700 bg-zinc-900 px-3 py-1 text-xs text-zinc-300 hover:border-indigo-500"
              >
                {t.topic} · {formatTimestamp(t.start_time)}
              </button>
            ))}
          </div>
        </Card>
      )}

      {report.opportunities.length > 0 && (
        <Card>
          <SectionTitle>Opportunities & Risks</SectionTitle>
          <div className="grid gap-3 md:grid-cols-2">
            {report.opportunities.map((o, i) => (
              <div key={i} className="rounded-xl border border-emerald-800/40 bg-emerald-950/20 p-4">
                <div className="flex items-center justify-between">
                  <Badge tone="emerald">{o.type}</Badge>
                  <span className="text-xs text-zinc-500">{pct(o.confidence)}</span>
                </div>
                <p className="mt-2 text-sm text-zinc-300">{o.description}</p>
                <EvidenceTimestamps timestamps={o.evidence_timestamps} onSeek={setSeekTo} />
              </div>
            ))}
            {report.risks.map((r, i) => (
              <div key={i} className="rounded-xl border border-rose-800/40 bg-rose-950/20 p-4">
                <div className="flex items-center justify-between">
                  <Badge tone="rose">{r.type}</Badge>
                  <span className="text-xs text-zinc-500">{pct(r.confidence)}</span>
                </div>
                <p className="mt-2 text-sm text-zinc-300">{r.description}</p>
                <EvidenceTimestamps timestamps={r.evidence_timestamps} onSeek={setSeekTo} />
              </div>
            ))}
          </div>
        </Card>
      )}

      {report.coaching.length > 0 && (
        <Card>
          <SectionTitle>Coaching</SectionTitle>
          <div className="space-y-4">
            {report.coaching.map((c, i) => (
              <div key={i} className="rounded-xl border border-zinc-800 bg-zinc-950/60 p-4">
                <div className="flex items-center gap-2">
                  <Badge tone={c.priority === "high" ? "rose" : c.priority === "medium" ? "amber" : "zinc"}>
                    {c.priority}
                  </Badge>
                  <span className="text-sm font-medium">{c.title}</span>
                </div>
                <p className="mt-2 text-sm text-zinc-300">{c.recommendation}</p>
                <p className="mt-1 text-xs text-zinc-500">{c.rationale}</p>
                {c.suggested_phrasing ? (
                  <p className="mt-2 rounded-lg bg-zinc-900 px-3 py-2 font-mono text-xs text-indigo-300">
                    {c.suggested_phrasing}
                  </p>
                ) : null}
                <EvidenceTimestamps timestamps={c.evidence_timestamps} onSeek={setSeekTo} />
              </div>
            ))}
          </div>
        </Card>
      )}

      {transcript && (
        <Card>
          <SectionTitle>Transcript</SectionTitle>
          <TranscriptView transcript={transcript} onSeek={setSeekTo} />
        </Card>
      )}
    </div>
  );
}

function AudioPanel({
  duration,
  audioRef,
}: {
  duration: number;
  audioRef: React.RefObject<HTMLAudioElement | null>;
}) {
  return (
    <Card className="border-indigo-800/40 bg-zinc-950">
      <div className="flex flex-wrap items-center gap-4">
        <span className="text-xs font-medium uppercase tracking-wider text-zinc-500">Recording</span>
        <audio ref={audioRef} controls className="h-10 min-w-0 flex-1" />
        <span className="font-mono text-xs text-zinc-500">{formatTimestamp(duration)}</span>
      </div>
      <p className="mt-2 text-xs text-zinc-500">
        Click any timestamp in the report to jump straight to that moment in the audio.
      </p>
    </Card>
  );
}

function RubricScoreRow({ score, onSeek }: { score: RubricScore; onSeek: (t: number) => void }) {
  const [open, setOpen] = useState(false);
  const r = score.result;
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-950/60">
      <button onClick={() => setOpen(!open)} className="flex w-full items-center gap-3 px-4 py-3 text-left">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate text-sm font-medium text-zinc-200">{score.label}</span>
            <span className="font-mono text-[10px] text-zinc-600">{score.dimension}</span>
          </div>
          <div className="mt-1.5 h-1.5 w-full rounded-full bg-zinc-800">
            <div
              className="h-1.5 rounded-full bg-gradient-to-r from-indigo-500 to-fuchsia-500"
              style={{ width: `${r.score * 10}%` }}
            />
          </div>
        </div>
        <div className="text-right">
          <div className={cx("text-lg font-semibold", scoreColor(r.score))}>{r.score.toFixed(1)}</div>
          <div className="flex items-center justify-end gap-1.5">
            <span className={cx("h-1.5 w-1.5 rounded-full", confidenceColor(r.confidence))} />
            <span className="text-[10px] text-zinc-500">{pct(r.confidence)}</span>
          </div>
        </div>
        <span className="text-xs text-zinc-600">{open ? "−" : "+"}</span>
      </button>
      {open && (
        <div className="border-t border-zinc-800/60 px-4 py-3">
          <p className="text-xs text-zinc-400">{r.reasoning}</p>
          {r.positive_evidence.length > 0 && (
            <div className="mt-3">
              <div className="text-[10px] font-semibold uppercase tracking-wider text-emerald-500">
                ✓ Demonstrates ({r.positive_evidence.length})
              </div>
              <EvidenceList evidence={r.positive_evidence} onSeek={onSeek} />
            </div>
          )}
          {r.negative_evidence.length > 0 && (
            <div className="mt-3">
              <div className="text-[10px] font-semibold uppercase tracking-wider text-rose-500">
                ✗ Contradicts ({r.negative_evidence.length})
              </div>
              <EvidenceList evidence={r.negative_evidence} onSeek={onSeek} />
            </div>
          )}
          {r.missing_behaviors.length > 0 && (
            <div className="mt-3">
              <div className="text-[10px] font-semibold uppercase tracking-wider text-amber-500">Missing behaviors</div>
              <ul className="mt-1 list-inside list-disc space-y-0.5 text-xs text-zinc-400">
                {r.missing_behaviors.map((b, i) => (
                  <li key={i}>{b}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function EvidenceList({ evidence, onSeek }: { evidence: Evidence[]; onSeek: (t: number) => void }) {
  return (
    <ul className="mt-1 space-y-2">
      {evidence.map((e, i) => (
        <li key={i} className="flex gap-2 text-xs">
          <button
            onClick={() => onSeek(e.start_time)}
            className="shrink-0 rounded-md bg-indigo-950 px-1.5 py-0.5 font-mono text-indigo-300 hover:bg-indigo-900"
            title="Jump to this moment in the audio"
          >
            {formatTimestamp(e.start_time)}
          </button>
          <div className="text-zinc-400">
            <span className="italic text-zinc-300">“{e.transcript_excerpt}”</span> — {e.explanation}
          </div>
        </li>
      ))}
    </ul>
  );
}

function EvidenceTimestamps({ timestamps, onSeek }: { timestamps: number[]; onSeek: (t: number) => void }) {
  if (!timestamps.length) return null;
  return (
    <div className="mt-2 flex flex-wrap gap-1.5">
      {timestamps.map((t, i) => (
        <button
          key={i}
          onClick={() => onSeek(t)}
          className="rounded-md bg-indigo-950 px-1.5 py-0.5 font-mono text-[10px] text-indigo-300 hover:bg-indigo-900"
        >
          {formatTimestamp(t)}
        </button>
      ))}
    </div>
  );
}

function TalkRatioCard({ metrics }: { metrics: NonNullable<CallReport["metrics"]> }) {
  const rep = metrics.talk_ratio.representative;
  const cust = metrics.talk_ratio.customer;
  return (
    <Card>
      <SectionTitle>Talk Ratio</SectionTitle>
      <div className="flex h-3 w-full overflow-hidden rounded-full">
        <div className="bg-indigo-500" style={{ width: `${rep * 100}%` }} />
        <div className="bg-fuchsia-500" style={{ width: `${cust * 100}%` }} />
        <div className="bg-zinc-700" style={{ width: `${metrics.talk_ratio.other * 100}%` }} />
      </div>
      <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
        <div className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full bg-indigo-500" />
          <span className="text-zinc-400">Representative</span>
          <span className="ml-auto font-semibold">{pct(rep)}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full bg-fuchsia-500" />
          <span className="text-zinc-400">Customer</span>
          <span className="ml-auto font-semibold">{pct(cust)}</span>
        </div>
      </div>
      <div className="mt-4 grid grid-cols-3 gap-2 border-t border-zinc-800 pt-3 text-center">
        <div>
          <div className="text-lg font-semibold">{metrics.words_per_minute.toFixed(0)}</div>
          <div className="text-[10px] uppercase tracking-wider text-zinc-500">wpm</div>
        </div>
        <div>
          <div className="text-lg font-semibold">{metrics.question_count}</div>
          <div className="text-[10px] uppercase tracking-wider text-zinc-500">questions</div>
        </div>
        <div>
          <div className="text-lg font-semibold">{metrics.interruptions}</div>
          <div className="text-[10px] uppercase tracking-wider text-zinc-500">interruptions</div>
        </div>
      </div>
    </Card>
  );
}

function SentimentCard({ report }: { report: CallReport }) {
  const sentiment = report.sentiment!;
  const segments = [
    ...(sentiment.representative?.timeline ?? []),
    ...(sentiment.customer?.timeline ?? []),
  ];
  const duration = report.metrics?.duration ?? 60;
  return (
    <Card>
      <SectionTitle>Customer Sentiment over time</SectionTitle>
      <div className="space-y-2">
        {segments.map((seg, i) => (
          <div key={i} className="flex items-center gap-2">
            <span className="w-16 shrink-0 text-[10px] uppercase tracking-wider text-zinc-500">
              {seg.speaker_id}
            </span>
            <div className="relative h-4 flex-1 rounded-full bg-zinc-800">
              <div
                className={cx(
                  "absolute inset-y-0 rounded-full",
                  seg.sentiment === "positive" || seg.sentiment === "enthusiastic"
                    ? "bg-emerald-500/70"
                    : seg.sentiment === "negative" || seg.sentiment === "frustrated"
                      ? "bg-rose-500/70"
                      : "bg-amber-500/60"
                )}
                style={{
                  left: `${(seg.start / duration) * 100}%`,
                  width: `${Math.max(3, ((seg.end - seg.start) / duration) * 100)}%`,
                }}
              />
            </div>
            <span className="w-24 shrink-0 text-right font-mono text-[10px] text-zinc-500">
              {formatTimestamp(seg.start)} · {seg.sentiment}
            </span>
          </div>
        ))}
      </div>
      <div className="mt-4 grid grid-cols-2 gap-2 text-center">
        {(
          [
            ["Engagement", sentiment.engagement],
            ["Frustration", sentiment.frustration],
            ["Enthusiasm", sentiment.enthusiasm],
            ["Objections", sentiment.objection_intensity],
          ] as const
        ).map(([label, value]) => (
          <div key={label} className="rounded-lg bg-zinc-950/60 p-2">
            <div className="text-sm font-semibold">{pct(value)}</div>
            <div className="text-[10px] uppercase tracking-wider text-zinc-500">{label}</div>
          </div>
        ))}
      </div>
    </Card>
  );
}

function TranscriptView({ transcript, onSeek }: { transcript: TranscriptModel; onSeek: (t: number) => void }) {
  return (
    <div className="max-h-96 space-y-3 overflow-y-auto pr-2">
      {transcript.utterances.map((u, i) => (
        <div key={i} className="flex gap-3">
          <button
            onClick={() => onSeek(u.start_time)}
            className="mt-0.5 shrink-0 rounded-md bg-zinc-900 px-1.5 py-0.5 font-mono text-[10px] text-zinc-400 hover:bg-indigo-950 hover:text-indigo-300"
          >
            {formatTimestamp(u.start_time)}
          </button>
          <div className="min-w-0">
            <div className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
              {u.speaker_id}
            </div>
            <p className="text-sm text-zinc-300">{u.text}</p>
          </div>
        </div>
      ))}
    </div>
  );
}
