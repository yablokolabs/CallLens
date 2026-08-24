# Contributing to CallLens

Thanks for contributing! CallLens is an open-source project, and the health of the codebase matters as much as the features.

## Development setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
calllens server          # API on :8000

cd apps/web
npm install
npm run dev              # dashboard on :3000
```

## Before you push

All checks must pass locally — CI runs exactly these:

```bash
ruff check .
ruff format --check .
mypy packages/calllens/src tests
pytest
cd apps/web && npm run lint && npm run typecheck && npm run build
```

## Engineering principles

1. **Type everything.** Domain objects are Pydantic models; graph state is a typed `TypedDict`.
2. **Deterministic where sufficient.** If it can be calculated, calculate it — don't ask an LLM.
3. **Structured LLM outputs only.** Never regex-parse model prose.
4. **Evidence for every semantic score.** New semantic outputs must cite timestamped evidence.
5. **Confidence on inferred outputs.** Attach and persist confidence.
6. **No paid APIs in tests or CI.** Add tests with mock providers; extend `calllens/testing.py` rather than hitting real services.
7. **Privacy is architectural.** Never log complete transcripts; never let secrets reach browser code or git.

## Tests

- `tests/unit` — metrics, rubric engine, evidence/confidence, parsers
- `tests/providers` — speech/LLM provider behavior (mocked)
- `tests/graphs` — LangGraph transitions, parallelism, confidence gate, bounded re-scoring
- `tests/api` — endpoint behavior with a TestClient
- `tests/evals` — harness + metrics correctness
- `tests/integration` — service + repository + SDK end to end

## Issues & PRs

- Use the issue templates for bug reports and feature requests.
- Keep PRs focused; reference the issue number.
- Never include API keys, transcripts of real people, or other sensitive data in issues, PRs, or commits.
