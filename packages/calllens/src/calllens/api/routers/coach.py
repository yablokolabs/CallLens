"""Coach API — agentic-ai over conversation-intelligence.

Exposes the Strands Coach Agent's autonomous decisions (NO_ACTION / COACH /
ESCALATE) with explainable-ai evidence and human-in-the-loop escalation.

Endpoints re-use CallLens analysis as the tool layer and add history + trace.
"""

from __future__ import annotations

import threading

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from calllens.api.deps import AppState
from calllens.coach.service import get_coach_service

router = APIRouter(prefix="/api/coach", tags=["coach"])


def _app(request: Request) -> AppState:
    return request.app.state.calllens


class AnalyzeBody(BaseModel):
    transcript: str
    rubric_name: str = "consultative_sales"
    rep_id: str | None = None
    call_id: str | None = None


@router.get("/summary")
async def coach_summary(request: Request) -> dict:
    svc = get_coach_service(_app(request).settings)
    return svc.summary()


@router.get("/calls")
async def coach_list_calls(request: Request) -> list[dict]:
    svc = get_coach_service(_app(request).settings)
    decs = svc.list_decisions()
    out: list[dict] = []
    for d in decs:
        out.append(
            {
                "id": d.call_id,
                "call_id": d.call_id,
                "decision": d.decision.value,
                "confidence": d.confidence,
                "summary": d.summary,
                "human_review_required": d.human_review_required,
                "created_at": None,
            }
        )
    return out


@router.get("/calls/{call_id}")
async def coach_get_call(request: Request, call_id: str) -> dict:
    svc = get_coach_service(_app(request).settings)
    dec = svc.get_decision(call_id)
    if dec is None:
        raise HTTPException(status_code=404, detail=f"coach decision for {call_id} not found")
    report = svc.get_report(call_id)
    return {
        "decision": dec.decision.value,
        "confidence": dec.confidence,
        "summary": dec.summary,
        "reason": dec.reason,
        "evidence": [e.model_dump(mode="json") for e in dec.evidence],
        "metrics": dec.metrics,
        "rubric_context": dec.rubric_context,
        "recommended_action": dec.recommended_action.model_dump(mode="json")
        if dec.recommended_action
        else None,
        "human_review_required": dec.human_review_required,
        "trace": [t.model_dump(mode="json") for t in dec.trace],
        "history_context": dec.history_context.model_dump(mode="json")
        if dec.history_context
        else None,
        "call_id": dec.call_id,
        "rubric_name": dec.rubric_name,
        "model_provider": dec.model_provider,
        "report": report.model_dump(mode="json") if report else None,
    }


@router.get("/reps/{rep_id}/history")
async def coach_rep_history(request: Request, rep_id: str) -> dict:
    svc = get_coach_service(_app(request).settings)
    return svc.rep_history(rep_id)


@router.post("/analyze")
async def coach_analyze(request: Request, body: AnalyzeBody) -> dict:
    if not body.transcript or not body.transcript.strip():
        raise HTTPException(status_code=400, detail="transcript is required")
    svc = get_coach_service(_app(request).settings)
    decision = await svc.evaluate_transcript(
        body.transcript,
        rubric_name=body.rubric_name,
        rep_id=body.rep_id,
        call_id=body.call_id,
    )
    return {
        "decision": decision.decision.value,
        "confidence": decision.confidence,
        "summary": decision.summary,
        "reason": decision.reason,
        "evidence": [e.model_dump(mode="json") for e in decision.evidence],
        "metrics": decision.metrics,
        "rubric_context": decision.rubric_context,
        "recommended_action": decision.recommended_action.model_dump(mode="json")
        if decision.recommended_action
        else None,
        "human_review_required": decision.human_review_required,
        "trace": [t.model_dump(mode="json") for t in decision.trace],
        "history_context": decision.history_context.model_dump(mode="json")
        if decision.history_context
        else None,
        "call_id": decision.call_id,
        "rubric_name": decision.rubric_name,
    }


@router.post("/seed")
async def coach_seed(request: Request) -> dict:
    """Seed DEMO_MODE data. For live providers seeds in background so /docs stays live."""
    svc = get_coach_service(_app(request).settings)
    try:
        provider = (
            svc.settings.coach_model_provider
            or svc.settings.model_provider
            or svc.settings.llm_provider
            or "mock"
        ).lower()
        is_live = provider not in ("mock", "")
    except Exception:
        is_live = False
    if is_live and not svc._decisions:  # type: ignore[attr-defined]
        if getattr(svc, "_seeding", False):
            return {"seeding": True, "seeded": 0, "decisions": [], "summary": svc.summary()}
        svc._seed_error = None  # type: ignore[attr-defined]
        svc._seeding = True  # type: ignore[attr-defined]

        def _bg_seed() -> None:
            try:
                svc.seed_demo()
            except Exception as e:
                svc._seed_error = str(e)[:500]  # type: ignore[attr-defined]
            finally:
                svc._seeding = False  # type: ignore[attr-defined]

        threading.Thread(target=_bg_seed, daemon=True).start()
        return {"seeding": True, "seeded": 0, "decisions": [], "summary": svc.summary()}
    decisions = svc.seed_demo()
    return {
        "seeded": len(decisions),
        "decisions": [
            {"call_id": d.call_id, "decision": d.decision.value, "confidence": d.confidence}
            for d in decisions
        ],
        "summary": svc.summary(),
    }
