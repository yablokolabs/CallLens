# CallLens Architecture

CallLens turns raw conversations into **structured, evidence-backed behavioral intelligence**. The pipeline is orchestrated by LangGraph, keeps deterministic computation separate from semantic reasoning, and isolates every external provider behind a protocol.

```
Audio / Video / Transcript
          │
          ▼
       Ingestion
          │
          ▼
 ElevenLabs Speech-to-Text
   + Speaker Diarization
   + Timestamps
          │
          ▼
 Transcript Normalization
          │
          ▼
       LangGraph
          │
 ┌────────┼────────────┐
 ▼        ▼            ▼
Metrics  Semantic     Rubric
         Analysis     Scoring
 │        │            │
 └────────┼────────────┘
          ▼
 Evidence Verification
          ▼
 Confidence / Re-scoring
          ▼
 Conversation Intelligence
          │
 ┌────────┼───────────────┐
 ▼        ▼               ▼
REST    MCP/GraphQL   Next.js UI
```

## Design principles

1. **Evidence-backed everything.** No semantic score is returned without timestamped evidence, and every evidence timestamp must resolve to a real utterance (verified deterministically — the excerpt comes from the transcript, never from the model's quote).
2. **Deterministic where possible.** Talk time, words-per-minute, turns, interruptions, silence, transitions, and question counts are pure, unit-tested Python. LLMs are reserved for genuinely semantic work.
3. **Multi-stage scoring.** Candidate evidence extraction → verification → scorer → consistency check → confidence gate → bounded re-judge. Not one giant prompt.
4. **Provider isolation.** `SpeechProvider` and `LLMProvider` protocols; business logic never imports vendor SDKs.
5. **Auditability.** Every analysis records model provider/name/version, prompt version, rubric version, and pipeline version.
6. **No paid APIs in tests or CI.** Mock providers are first-class.

## Repository layout

```
apps/web/                         Next.js dashboard
packages/calllens/src/calllens/
  domain/                         Pydantic domain models
  metrics/                        deterministic conversation metrics
  rubrics/                        declarative rubric loader/validator/engine
  scoring/                        evidence, consistency, confidence, pipeline
  semantic/                       sentiment, topics, intents, opportunities, coaching
  providers/speech/elevenlabs/    STT + TTS integration (Scribe v2)
  providers/llm/                  openai / anthropic / compatible / mock
  graphs/                         LangGraph state + pipeline
  evals/                          evaluation harness + synthetic dataset
  storage/                        repository abstraction (memory + SQL)
  api/                            FastAPI app, routers, jobs
  sdk/                            async Python SDK client
mcp-server/                       MCP server (mcpize-deployable)
rubrics/                          bundled declarative rubrics
evals/                            datasets, fixtures, reports
docs/                             architecture, data model, langgraph, elevenlabs
```

## Pipeline stages

| Stage | Implementation | AI? |
| --- | --- | --- |
| Ingest / transcribe | `SpeechProvider.transcribe` (ElevenLabs Scribe v2, word-level timestamps + diarization; mock offline) | Speech API |
| Normalize | speaker roles, duration fallback | deterministic |
| Metrics | `calllens.metrics.compute_call_metrics` | none |
| Sentiment / topics / intents | `calllens.semantic.*` with structured output schemas | LLM |
| Rubric scoring | per-dimension: evidence extraction → verification → score → consistency → confidence | LLM + deterministic gates |
| Opportunities / risks | `OpportunityDetector` | LLM |
| Confidence gate | weighted dimension confidence vs `CONFIDENCE_THRESHOLD`; bounded re-judge (`MAX_RESCORE_ATTEMPTS`) | deterministic |
| Coaching | generated from rubric results with timestamped evidence | LLM |
| Report | `CallReport` assembled in the `report` node | — |

## Confidence

Final dimension confidence combines three signals:

```
confidence = model_confidence × evidence_coverage_factor × consistency_factor
```

- **evidence_coverage_factor** = how much of the extracted candidate evidence survived deterministic verification.
- **consistency_factor** = deterministic heuristics penalizing contradictions (e.g. high score with more negative than positive evidence, or near-perfect score with missing behaviors).

## Async processing

Call analysis can take minutes, so expensive work never runs inside an HTTP request lifetime. `calllens.api.jobs` defines a minimal `JobQueue` protocol with an in-process asyncio implementation for local development; Redis/Celery/SQS adapters can implement the same interface in production. Call states (`UPLOADED → TRANSCRIBING → TRANSCRIBED → ANALYZING → VERIFYING → COMPLETED/FAILED`) are persisted.

## Multi-tenancy & storage

- Every business record carries an `organization_id`; repository methods scope by it.
- `Repository` protocol with two implementations: `InMemoryRepository` (tests, demos) and `SQLRepository` (SQLAlchemy async — SQLite locally, PostgreSQL/Supabase/RDS in production).
- Reports are stored as JSON documents alongside a light relational core.

## Production (AWS)

`infra/aws/` sketches the production topology: ECS/Fargate services, RDS PostgreSQL (or Supabase), S3 for recordings (private + signed URLs), SQS for jobs, CloudWatch for logs/metrics, Secrets Manager for keys. Local development never requires AWS — `docker compose up` is the whole local environment.

## Live mode & role-play (future)

The provider abstractions already make live mode (ElevenLabs realtime STT → streaming LangGraph state → live coaching signals) and role-play mode (rep ↔ AI customer, evaluated by the same rubric engine) incremental rather than rewrites. Neither is built before the recorded-call MVP is solid.
