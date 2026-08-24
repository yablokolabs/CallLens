"""Representative analytics endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request

from calllens.api.deps import AppState
from calllens.domain.report import CallReport
from calllens.storage.base import RecordNotFound

router = APIRouter(prefix="/api/v1/reps", tags=["reps"])


def _app(request: Request) -> AppState:
    return request.app.state.calllens


@router.get("/{rep_id}/analytics")
async def rep_analytics(request: Request, rep_id: str) -> dict:
    """Aggregate per-representative analytics across analyzed calls.

    Note: long-term performance must never be judged from a single call;
    this aggregates whatever reports exist for the representative.
    """
    state = _app(request)
    calls = await state.repository.list_calls(organization_id=state.organization_id)
    reports: list[CallReport] = []
    for call in calls:
        try:
            reports.append(
                await state.repository.get_report(call["id"], organization_id=state.organization_id)
            )
        except RecordNotFound:
            continue

    dimension_totals: dict[str, list[float]] = {}
    confidences: list[float] = []
    for report in reports:
        if report.confidence is not None:
            confidences.append(report.confidence)
        for score in report.rubric_scores:
            dimension_totals.setdefault(score.dimension, []).append(score.result.score)

    dimensions = {dim: round(sum(vals) / len(vals), 1) for dim, vals in dimension_totals.items()}
    avg = round(sum(dimensions.values()) / len(dimensions), 1) if dimensions else 0.0
    return {
        "rep_id": rep_id,
        "calls_analyzed": len(reports),
        "average_score": avg,
        "dimensions": dimensions,
        "average_confidence": round(sum(confidences) / len(confidences), 3) if confidences else 0.0,
        "trend": _trend_note(len(reports)),
    }


def _trend_note(n: int) -> str:
    if n < 3:
        return (
            "Insufficient calls for a trend — do not judge long-term "
            "performance from a single call."
        )
    return (
        "Trend available once representative identity is linked to calls "
        "(MVP stores org-scoped calls)."
    )
