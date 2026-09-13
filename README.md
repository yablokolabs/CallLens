# CallLens

**Open-source conversation intelligence and behavioral evaluation powered by LangGraph — plus CallLens Coach, the autonomous manager that decides what happens next.**

> Upload a call. CallLens transcribes it, reconstructs the conversation, measures deterministic communication metrics, evaluates semantic behaviors against configurable rubrics, verifies the supporting evidence, and produces explainable conversation intelligence.
>
> **CallLens Coach** then asks: *"Given what happened in this conversation, should anything happen next?"* — and autonomously chooses **NO_ACTION · COACH · ESCALATE**, with evidence, not vibes.

CallLens turns raw conversations — recordings or transcripts — into **structured, evidence-backed behavioral intelligence**: diarized transcripts, talk-time and pace metrics, longitudinal sentiment, topics, opportunity/risk detection, and per-representative analytics, all scored against declarative, versioned rubrics.

**Every semantic score is evidence-backed.** Never just `Discovery: 8/10`. Instead:

```
Discovery: 8.7/10
Confidence: 0.91

Evidence:
  04:32  Representative asks customer about their current operational bottleneck.
  05:17  Representative asks about business impact.
  07:02  Customer explains delivery delays.

Missing behavior:
  Representative never established urgency or implementation timeframe.
```

Users click a timestamp and the audio player **jumps to that exact moment**.

---

## The Problem

Managers shouldn't listen to 30 calls to discover the one conversation that needs their attention. Most tools are dashboards that generate *more* analysis to read. They don't answer whether a human should intervene, coach, or do nothing — so attention is wasted and coaching is inconsistent.

## The Solution

**CallLens Coach** is an autonomous manager built as an add-on in this same repository. CallLens remains the specialized conversation-intelligence engine (transcribe → metrics → rubric scoring → evidence verification). **Strands Agents SDK is the decision layer on top**: it receives a call analysis, calls tools when needed, inspects evidence and deterministic metrics, consults lightweight rep history, and produces an explainable **NO_ACTION / COACH / ESCALATE** decision — with the correct behavior often being to stay silent.

> The product is not valuable because it generates more AI output. It is valuable because it **returns human attention only when human attention is useful**.

---

## Demo

Interactive diagrams (full branded HTML) live in [`docs/diagrams/`](docs/diagrams/) — open them directly in a browser:

- [`architecture.html`](docs/diagrams/architecture.html) · [`agent-flow.html`](docs/diagrams/agent-flow.html) · [`decision-flow.html`](docs/diagrams/decision-flow.html)

A single-screen Coach dashboard is the design target:

```
CALLLENS COACH

TODAY
18 calls analyzed

15  No action required
 2  Coaching generated
 1  Manager review required

Sarah — Acme Corp        ✓ No action
Daniel — Northstar       ⚠ Coaching generated  · Discovery · Talk balance → View evidence
Maya — Contoso           🔴 Manager review required · Customer churn risk → View evidence
```

For a selected call, an agent activity trace (no hidden chain-of-thought) and an evidence panel with metric, rubric, timestamps, and recommended action are shown. See **Demo Mode** below for the three deterministic scenarios (healthy → NO_ACTION, coaching → COACH, churn → ESCALATE).

---

## How It Works

### CallLens baseline (existing)

Audio or transcript → ElevenLabs Scribe v2 (STT + diarization) → transcript normalization → **LangGraph** orchestration: deterministic metrics (talk ratio, wpm, interruptions, turns, silences) in parallel with semantic analysis (sentiment, topics, intents) and per-dimension rubric scoring (evidence extraction → verification → scoring → consistency → confidence gate → bounded re-judge) → coaching → `CallReport`.

### Coach layer (new, same repo)

```
User / Calls
    ↓
Next.js Dashboard (/coach)
    ↓
FastAPI (/api/coach/*)
    ↓
Strands Coach Agent
    ↓
CallLens MCP / Analysis  +  Rep History (SQLite, 5-call window)
    ↓
Evidence + Metrics + History
    ↓
Decision
 ├── NO_ACTION — healthy, no interruption warranted
 ├── COACH — targeted coaching with evidence + metric + rubric + suggestion
 └── ESCALATE → Human Manager — churn / risk / compliance / ambiguity
```

Deterministic escalation signals are checked first; rubric+evidence is second; historical pattern (e.g. “discovery issue in 4/5 calls”) gates COACH so a single isolated low score does not trigger coaching.

---

## Why This Is an Agent

This is not another analytics dashboard. The agent **makes an autonomous decision** per conversation and triggers the appropriate action — or explicitly does nothing. It:

1. receives/contextualizes a call analysis
2. calls tools when needed (`analyze_call`, `get_call_evidence`, `get_rep_history`, `get_available_rubrics`, `create_coaching_action`, `escalate_to_manager`, `record_agent_decision`)
3. inspects evidence and deterministic metrics (not just LLM vibes)
4. determines whether additional information is required
5. decides NO_ACTION vs COACH vs ESCALATE
6. generates an explainable reason with timestamps
7. triggers the appropriate action/tool
8. knows when human involvement is required

LangGraph is *not* ported to Strands line-for-line. CallLens *is* the evidence layer; Strands *is* the orchestration layer.

---

## Architecture

Branded diagrams are generated with [`cathrynlavery/diagram-design`](https://github.com/cathrynlavery/diagram-design) and skinned to the CallLens brand (`zinc-950 #09090b`, `indigo-500 #6366f1` focal, zinc neutrals — matching `apps/web` `from-indigo-500 to-fuchsia-500`). The style guide lives at `.agents/skills/diagram-design/references/style-guide.md`.

### System overview — Strands is the decision layer, CallLens is the evidence layer

![CallLens Coach architecture](docs/diagrams/architecture.svg)

*Interactive: [`docs/diagrams/architecture.html`](docs/diagrams/architecture.html)*

### Agent trace — one call, one autonomous review

![Agent flow](docs/diagrams/agent-flow.svg)

*Interactive: [`docs/diagrams/agent-flow.html`](docs/diagrams/agent-flow.html)*

The Strands agent calls `ANALYZE_CALL` → `GET_EVIDENCE` → `GET_HISTORY`, then enters an `ALT` fragment: `NO_ACTION (0.89)`, `COACH (0.91 + evidence)`, or `ESCALATE → human`. Human-in-the-loop only on ESCALATE; COACH is explainable with timestamps.

### Decision logic — should anything happen next?

![Decision logic](docs/diagrams/decision-flow.svg)

*Interactive: [`docs/diagrams/decision-flow.html`](docs/diagrams/decision-flow.html)*

Escalation signals (churn, anger, risk) win first. Otherwise rubric + evidence is evaluated, then rep history gates coaching: a repeated pattern (e.g. 4/5) → COACH, an isolated miss → NO_ACTION. Staying silent is a correct outcome.

Existing CallLens pipeline detail:

```mermaid
flowchart TD
    A[Audio / Transcript] --> B[Ingestion]
    B --> C[ElevenLabs STT + Diarization]
    C --> D[Transcript Normalization]
    D --> E[LangGraph]
    E --> F[Deterministic Metrics]
    E --> G[Semantic Analysis]
    G --> H[Sentiment]
    G --> I[Topics]
    G --> J[Intents]
    F --> K[Evidence Verification]
    H --> K
    I --> K
    J --> K
    K --> L[Confidence Gate]
    L -->|sufficient| M[Report]
    L -->|insufficient| N[Bounded Re-score]
    N --> K
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/LANGGRAPH.md](docs/LANGGRAPH.md), and [docs/DATA_MODEL.md](docs/DATA_MODEL.md). Full diagram sources are `docs/diagrams/*.html` (branded HTML) and `docs/diagrams/*.svg` (portable SVG) — both generated from the same inline SVG.

---

## Strands Agents SDK

Strands Agents SDK is central to the Coach implementation. The Coach agent owns the loop — CallLens never drives the decision. The agent is given a small, typed toolset and must decide when to call tools, when it has enough evidence, and when to stop:

- `analyze_call(transcript, rubric)` — run the full CallLens pipeline
- `get_call_evidence(call_id, dimension)` — retrieve verified evidence with timestamps
- `get_rep_history(rep_id)` — last 5 calls, pattern counts (e.g. discovery miss 4/5)
- `get_available_rubrics()` — list declarative rubrics
- `create_coaching_action(call_id, message, evidence)` — emit a COACH action
- `escalate_to_manager(call_id, reason, evidence, urgency)` — emit ESCALATE
- `record_agent_decision(decision)` — persist the structured result (confidence, summary, evidence, metrics, human_review_required)

Every completed evaluation produces a structured decision:

```json
{
  "decision": "COACH",
  "confidence": 0.91,
  "summary": "The rep did not sufficiently explore the customer's underlying requirements.",
  "evidence": [{ "timestamp": "00:02:14", "quote": "...", "reason": "Pricing concern answered without a discovery question." }],
  "metrics": { "rep_talk_ratio": 0.79 },
  "recommended_action": { "type": "COACH", "message": "Pause after a concern and ask one discovery question before proposing a solution." },
  "human_review_required": false
}
```

`ESCALATE` sets `human_review_required: true`; `NO_ACTION` explains why no interruption was warranted. No hidden chain-of-thought is exposed — only a concise activity trace and user-facing rationale.

Provider abstraction is preserved so Bedrock can be enabled via configuration (see **Configuration**). Local development defaults to the deterministic mock LLM — no paid calls required.

---

## MCP Integration

CallLens already ships an MCP server (`mcp-server/server.py`, deployable via `mcpize`) exposing:

- `analyze_transcript(transcript, rubric)` — full pipeline over a transcript
- `score_dimension(transcript, dimension, rubric)` — evidence-backed single-dimension score
- `list_rubrics()` — available declarative rubrics and dimensions

The Coach agent consumes CallLens through MCP (or a clean tool adapter that wraps the same calls) — no fake integrations. Strands = autonomous orchestration; CallLens = specialized evidence/intelligence. See [mcpize.yaml](mcpize.yaml).

```bash
mcpize analyze && mcpize doctor && mcpize deploy
# Local stdio:
pip install -r requirements.txt
python mcp-server/server.py
```

---

## Explainability

Every COACH or ESCALATE decision is explainable through:

- transcript evidence with timestamp(s)
- relevant deterministic metric(s) (e.g. rep talk ratio 79%, discovery 42/100)
- relevant rubric criterion
- confidence
- short rationale

Example: *“Discovery 42/100 · Rep talk ratio 79% · Evidence at 02:14 — pricing concern answered without a discovery question. Coaching: pause and ask one discovery question before proposing a solution.”* Vague outputs like “The AI thinks this call was poor” are avoided.

---

## Human-in-the-Loop

The agent demonstrates sensible boundaries. High-impact or ambiguous decisions surface as **Manager review required** with reason, evidence, urgency, and recommended next action. The agent never takes irreversible real-world actions autonomously. For the demo, one escalation scenario makes manager review visibly required.

---

## Tech Stack

`strands-agents-sdk` · `python` · `fastapi` · `nextjs` · `typescript` · `mcp` · `ai-agents` · `agentic-ai` · `conversation-intelligence` · `sales-coaching` · `human-in-the-loop` · `explainable-ai` · `langgraph` · `elevenlabs` · `sqlalchemy` · `docker`

---

## Local Development

### Docker (recommended)

```bash
cp .env.example .env
docker compose up
```

- API + OpenAPI docs: http://localhost:8000/docs
- Dashboard: http://localhost:3000
- Coach: http://localhost:3000/coach

No API keys are required to try it: without `ELEVENLABS_API_KEY` the speech provider and reasoning LLM fall back to deterministic offline mocks, so the full pipeline (transcribe → metrics → evidence-backed rubric scoring → coaching) runs end to end.

### Local (Python)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Analyze a transcript (offline, deterministic)
calllens analyze sample.txt

# Start the API server
calllens server

# Run the evaluation harness
calllens eval run
```

### Frontend

```bash
cd apps/web
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

## CLI

```bash
calllens analyze call.mp3
calllens analyze call.mp3 --rubric consultative_sales --output report.json
calllens rubric list
calllens rubric validate ./my_rubric.yaml
calllens eval run
calllens server
```

## Python SDK

```python
import asyncio
from calllens import CallLens


async def main():
    async with CallLens(base_url="http://localhost:8000") as client:
        call = await client.calls.upload("sales-call.mp3")
        await call.analyze(rubric="consultative_sales")
        report = await call.report()
        print(report["overall_score"], report["confidence"])


asyncio.run(main())
```

## REST API (subset)

```
POST   /api/v1/calls                     upload a recording or transcript
GET    /api/v1/calls
GET    /api/v1/calls/{id}
POST   /api/v1/calls/{id}/analyze
GET    /api/v1/calls/{id}/analysis       the evidence-backed CallReport
GET    /api/v1/calls/{id}/transcript
DELETE /api/v1/calls/{id}                privacy/retention deletion
POST   /api/v1/rubrics                   register a declarative rubric
GET    /api/v1/rubrics
POST   /api/v1/rubrics/validate
GET    /api/v1/reps/{id}/analytics
POST   /api/v1/evals/run

# Coach (add-on)
POST   /api/coach/analyze
GET    /api/coach/calls
GET    /api/coach/calls/{id}
GET    /api/coach/reps/{id}/history
GET    /api/coach/summary
```

Interactive docs at `/docs`.

---

## Demo Mode

```env
DEMO_MODE=true
```

In demo mode synthetic calls are seeded and the three scenarios are available instantly with deterministic results — no paid transcription or live third-party dependency. A **Load Demo Calls** action (or auto-seed) makes them navigable without terminal commands.

| Scenario | Expected decision | Signal |
|---|---|---|
| **A — healthy call** | `NO_ACTION` | Balanced talk, good discovery, clear next step, no major concern |
| **B — coaching needed** | `COACH` | Rep dominates, misses discovery, jumps to solution — with evidence |
| **C — escalation** | `ESCALATE` | Serious dissatisfaction / churn signal — manager review required |

---

## Configuration

See [`.env.example`](.env.example). Key vars:

| Var | Purpose | Required |
|---|---|---|
| `ELEVENLABS_API_KEY` | Speech provider (Scribe v2) | No — mock fallback |
| `LLM_PROVIDER` | `mock` (default) · `openai` · `anthropic` · `compatible` · `bedrock` | No |
| `LLM_MODEL` / `MODEL_ID` | Model id for the selected provider | No |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | Vendor keys | If provider selected |
| `COMPATIBLE_BASE_URL` / `COMPATIBLE_API_KEY` | OpenAI-compatible endpoint | If `compatible` |
| `MODEL_PROVIDER` / `BEDROCK_MODEL_ID` / `AWS_REGION` / `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | Bedrock (enabled via config, fallback preserved) | No — only if Bedrock is used |
| `DATABASE_URL` | `postgresql+asyncpg://…` or `sqlite+aiosqlite://…` | No — defaults to SQLite |
| `CONFIDENCE_THRESHOLD` / `MAX_RESCORE_ATTEMPTS` | Pipeline knobs | No |
| `DEMO_MODE` | Seed synthetic demo calls | No |
| `NEXT_PUBLIC_API_URL` | Frontend API base | No — defaults to `http://localhost:8000` |

Bedrock is designed as a configuration switch (model-provider abstraction), not a migration. The app runs on Azure VM by default; Bedrock is only claimed when actually implemented and tested.

---

## Rubrics

Rubrics are **declarative and versioned** YAML documents. The engine itself is generic — sales is just the first bundled rubric. Bring your own: customer support, recruitment, collections, insurance, real estate, customer success, interviews, AI voice agents.

```yaml
name: consultative_sales
version: "1.0"
dimensions:
  rapport:
    label: Rapport
    weight: 0.08
  discovery:
    label: Problem Discovery
    weight: 0.16
```

Dimension weights must sum to `1.0`. See [rubrics/](rubrics/) and [docs/custom-rubrics](docs/CUSTOM_RUBRICS.md).

## Providers

| Layer | Provider | Config |
| --- | --- | --- |
| Speech (STT/TTS) | ElevenLabs Scribe v2 | `ELEVENLABS_API_KEY`, `ELEVENLABS_STT_MODEL` |
| Reasoning LLM | OpenAI | `LLM_PROVIDER=openai`, `OPENAI_API_KEY`, `LLM_MODEL` |
| Reasoning LLM | Anthropic | `LLM_PROVIDER=anthropic`, `ANTHROPIC_API_KEY`, `LLM_MODEL` |
| Reasoning LLM | Any OpenAI-compatible endpoint | `LLM_PROVIDER=compatible`, `COMPATIBLE_BASE_URL`, `COMPATIBLE_API_KEY` |
| Reasoning LLM | Amazon Bedrock | `MODEL_PROVIDER=bedrock`, `AWS_REGION`, `BEDROCK_MODEL_ID` |
| Reasoning LLM | Offline mock (default) | `LLM_PROVIDER=mock` |

All tests and CI run against mocks — no paid API calls.

### Example: live analysis with real providers

Wire both providers in `.env` and analyze an actual recording:

```bash
# .env — speech + reasoning
ELEVENLABS_API_KEY=sk_...
ELEVENLABS_STT_MODEL=scribe_v2

# Any OpenAI-compatible endpoint, e.g. Melious (https://api.melious.ai/v1)
LLM_PROVIDER=compatible
COMPATIBLE_BASE_URL=https://api.melious.ai/v1
COMPATIBLE_API_KEY=sk-mel-...
LLM_MODEL=gpt-oss-120b
```

Then run the full pipeline on a recording — it must be a pre-recorded call file
(MP3/WAV), but you can synthesize one if you don't have a recording handy:

```bash
# Option A — you have a recording: transcribe + analyze it live
# (Scribe v2 STT → metrics → evidence-backed scoring → coaching)
calllens analyze call.mp3 --rubric consultative_sales --output report.json

# Option B — no recording? Synthesize a two-speaker sample call with ElevenLabs TTS
python examples/generate_sample_call.py   # → sample_call.mp3
calllens analyze sample_call.mp3 --rubric consultative_sales --output report.json

# Both write the evidence-backed report (scores + timestamped evidence + coaching)
# to report.json; omit --output to print it to stdout.
```

> The `compatible` endpoint must support OpenAI JSON-schema structured outputs
> (`response_format: {type: "json_schema"}`) — the pipeline's `structured_completion`
> depends on it. Not every model on every gateway does; e.g. `gpt-oss-120b` on
> Melious works, while several others (GLM, Kimi, DeepSeek v4 on Melious) reject
> schema mode. Probe with a small structured call before committing to a model.

## Evaluation

```text
| Dimension | MAE | Correlation |
|-----------|-----|-------------|
| Discovery | .61 | .88         |
| Rapport   | .74 | .81         |
```

The harness ([`calllens.evals`](packages/calllens/src/calllens/evals/)) runs the full pipeline over a 13-scenario synthetic dataset (excellent seller, poor seller, weak discovery, angry customer, multilingual, …) and reports MAE, RMSE, correlation, and evidence precision/recall against human-quality labels.

---

## Testing

```bash
pip install -e ".[dev]"
pytest -q
```

Tests cover healthy → NO_ACTION, coaching → COACH, escalation → ESCALATE, decision-schema validation, evidence presence for COACH/ESCALATE, `human_review_required` for escalations, and API smoke tests. Model calls are mocked — CI never depends on live LLM APIs.

---

## Deployment

Target is the existing Linux Azure VM. Application hosting may remain Azure; Bedrock/AgentCore are not required for the first working version.

- `.env.example` documents all vars
- Docker: `Dockerfile.backend` + `Dockerfile.frontend` + `docker-compose.yml`
- Health endpoint: `GET /health` → `{ status: "ok", llm_provider }`
- Production start:

```bash
cp .env.example .env  # then set real values — never commit secrets
docker compose up --build -d
# or
uvicorn calllens.api:create_app --factory --host 0.0.0.0 --port 8000
cd apps/web && npm run build && npm start
```

See `infra/` for AWS sketches (ECS/RDS/S3/SQS) — not required for the local/Azure path.

---

## Pre-existing Work & Hackathon Contributions

**CallLens is pre-existing.** It is an existing Yabloko Labs conversation-intelligence project that already provides transcript ingestion, ElevenLabs transcription/diarization, deterministic metrics, LangGraph-orchestrated semantic analysis, multi-stage evidence-backed rubric scoring with verification and confidence gating, rubrics, MCP server/tools, provider/model abstraction (OpenAI/Anthropic/compatible/mock + ElevenLabs), persistence (memory + SQLAlchemy), REST API, Python SDK/CLI, evaluation harness, and Next.js dashboard. That functionality is reused as the **conversation-analysis capability/tool layer** — not rewritten.

**CallLens Coach is the new hackathon work.** It is the autonomous decision-making layer built in this same repository as an add-on (see **Architecture**):

- Strands Agents SDK as the central orchestration loop (tool calling, evidence inspection, NO_ACTION/COACH/ESCALATE decision, explainable rationale, human-in-the-loop escalation)
- Coach action tools (`analyze_call`, `get_call_evidence`, `get_rep_history`, `get_available_rubrics`, `create_coaching_action`, `escalate_to_manager`, `record_agent_decision`) and clean MCP adaptation of existing CallLens tools
- Longitudinal rep history / context (lightweight SQLite, 5-call window) so repeated patterns can be distinguished from isolated misses
- Demo workflow with three synthetic scenarios and a one-screen Coach dashboard (`/coach`) showing summary, call list, agent activity trace, and evidence panel — designed so “doing nothing” is visible as correct behavior
- Branded architecture diagrams (`docs/diagrams/*.html` + `*.svg`) generated with `cathrynlavery/diagram-design` and skinned to the CallLens brand

If code is copied or adapted from CallLens, it is documented. Integration/reuse is preferred over duplicating large amounts of existing source. For Devpost, if a distinct `calllens-coach` repository name is required, this same repository can be pushed to a new remote — history is preserved and originality remains clear via this section and `git log`.

---

## Security & privacy

- API keys are environment-only; nothing is ever committed, logged, or exposed to the browser.
- Call recordings are treated as sensitive: tenant isolation, private/signed storage, deletion and configurable retention.
- Complete transcripts are never logged by default.
- See [SECURITY.md](SECURITY.md) and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## License

[MIT](LICENSE) © Yabloko Labs
