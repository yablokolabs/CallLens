"""Evaluation endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from calllens.api.deps import AppState
from calllens.evals.harness import EvaluationResult
from calllens.evals.synthetic import generate_synthetic_dataset

router = APIRouter(prefix="/api/v1/evals", tags=["evals"])


def _app(request: Request) -> AppState:
    return request.app.state.calllens


@router.post("/run")
async def run_eval(request: Request, payload: dict | None = None) -> EvaluationResult:
    """Run the evaluation harness over the synthetic dataset."""
    state = _app(request)
    scenarios = (payload or {}).get("scenarios")
    rubric = state.rubrics.get((payload or {}).get("rubric", "consultative_sales"))
    if rubric is None:
        raise HTTPException(status_code=404, detail="rubric not found")
    calls = generate_synthetic_dataset(scenarios=scenarios)
    from calllens.evals.harness import EvaluationHarness

    harness = EvaluationHarness(rubric, speech=state.speech, llm=state.llm)
    return await harness.evaluate(calls)
