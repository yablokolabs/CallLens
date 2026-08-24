# Data Model

All domain objects are Pydantic v2 models in `packages/calllens/src/calllens/domain/`. Timestamps are **seconds (float) relative to the start of the recording**.

## Core objects

```
Transcript
├── utterances: list[Utterance]      speaker_id, text, start_time, end_time
├── speakers:   list[Speaker]        id, label, role (representative|customer|unknown)
├── language, source, duration
```

```
CallReport
├── overall_score: float (0–100)          weighted rubric total
├── confidence: float (0–1)
├── metrics: CallMetrics | None
├── sentiment: SentimentAnalysis | None
├── topics: list[Topic]
├── rubric_scores: list[RubricScore]
├── opportunities: list[Opportunity]
├── risks: list[Risk]
├── coaching: list[CoachingInsight]
├── model_identity: ModelIdentity         provider/model/prompt/rubric/pipeline versions
└── usage: UsageRecord                    tokens, STT seconds, estimated cost
```

## Scoring objects

```
RubricResult (per dimension)
├── score: float (0–10)
├── confidence: float (0–1)
├── reasoning: str
├── positive_evidence: list[Evidence]
├── negative_evidence: list[Evidence]
└── missing_behaviors: list[str]

Evidence
├── start_time / end_time                seconds
├── speaker_id
├── transcript_excerpt                   ALWAYS rebuilt from the real transcript
└── explanation, kind (positive|negative)
```

`RubricScore` wraps a `RubricResult` with the rubric's label and weight so dashboards can render directly.

## Rubric model

```
Rubric { name, version, description, dimensions[] }
RubricDimension { key, label, weight (sums to 1.0), description }
```

Rubrics are declarative YAML (see `rubrics/`), validated on load; the engine is generic, so sales, support, recruitment, and custom rubrics share one code path.

## Persistence (PostgreSQL / Supabase)

Relational core (`calllens.storage.sql`):

```
calls            id, organization_id, filename, status, created_at
transcripts      call_id, organization_id, transcript_json
reports          call_id, organization_id, report_json
analysis_runs    id, call_id, organization_id, status, rubric_name, error, created_at
```

Multi-tenancy is designed in from day one: `organization_id` on every table, scoping in every repository method, and row-level security to be enabled in Supabase (see `docs/ARCHITECTURE.md`).

## Auditability

Every analysis stores a `ModelIdentity`:

```
model_provider, model_name, model_version,
prompt_version, rubric_version, pipeline_version
```

plus a `UsageRecord` (input/output tokens, STT seconds, requests, estimated cost). This is the foundation for drift monitoring: sentiment/score/confidence distributions can be compared across model or prompt changes.
