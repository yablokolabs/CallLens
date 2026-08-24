# Roadmap

The MVP goal: a user can upload a recording, pick a rubric, watch processing status, read the diarized transcript, play synchronized audio, see talk-time ratios, sentiment, topics, rubric scores, click evidence timestamps to seek audio, read coaching, and export structured JSON — **that works today**.

## Shipped

- [x] LangGraph analysis pipeline (parallel fan-out, confidence gate, bounded re-scoring)
- [x] ElevenLabs STT + TTS provider (Scribe v2, word timestamps + diarization) with mock fallback
- [x] LLM provider abstraction (OpenAI, Anthropic, OpenAI-compatible, mock)
- [x] Deterministic conversation metrics
- [x] Multi-stage, evidence-backed rubric scoring + evidence verification + confidence
- [x] Sentiment (longitudinal), topics, intents, opportunities/risks, coaching
- [x] Declarative versioned rubrics + generic rubric engine
- [x] FastAPI REST API + async job abstraction + status persistence
- [x] Python SDK + CLI (`analyze`, `rubric`, `eval`, `server`)
- [x] Evaluation harness + 13-scenario synthetic dataset
- [x] Next.js dashboard (upload, calls, call detail with audio seeking, reps, rubrics, analytics)
- [x] MCP server + MCPize deployment config
- [x] Docker compose local environment, GitHub Actions CI
- [x] Repository abstraction (memory + SQLAlchemy; PostgreSQL/Supabase-ready)

## Next

1. **Supabase integration** — auth, row-level security, private object storage with signed URLs for recordings.
2. **Job backends** — Redis/Celery and SQS adapters for the `JobQueue` protocol.
3. **Representative identity & trends** — link calls to representatives; 30-day per-dimension trend deltas.
4. **GraphQL dashboard queries** — a thin GraphQL layer over the REST API for analytics dashboards.
5. **Drift monitoring** — distribution comparisons (sentiment, scores, confidence) across model/prompt/rubric changes, using the per-analysis `ModelIdentity`.
6. **Retention & deletion policies** — configurable retention tiers and background cleanup jobs.
7. **Human-in-the-loop** — LangGraph checkpoint resume for evidence review and manual score overrides.

## Later

- **Live mode** — ElevenLabs realtime STT → streaming LangGraph state → live coaching signals ("Pricing objection detected", "You've spoken continuously for 3m 12s").
- **Role-play mode** — representative vs. AI customer personas (skeptical prospect, enterprise buyer, angry customer, …), evaluated by the same rubric engine at the end.
- **Custom rubric marketplace** — share and import org-specific rubrics.
- **CRM integrations** — push scores/coaching into Salesforce/HubSpot.
- **Billing & enterprise SSO** — deferred until the primary workflow is reliable.
