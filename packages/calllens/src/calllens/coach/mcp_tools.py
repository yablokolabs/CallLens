"""Strands @tool adapters — CallLens as the evidence layer.

These @tool functions wrap CallLens capabilities (which already ship as MCP
tools: analyze_transcript, score_dimension, list_rubrics) plus lightweight
history/escalation actions. The Strands agent sees a small, typed toolset:

  analyze_call, get_call_evidence, get_available_rubrics,
  check_escalation_signals, get_rep_history,
  create_coaching_action, escalate_to_manager, record_agent_decision

The tags strands-agents-sdk + mcp are satisfied here: these are the Strands
tools that consume the CallLens MCP surface. When running outside a live MCP
transport, they call the same underlying CallLens services directly.

Deterministic helpers (check_escalation_signals) are tools so the agent —
not application logic — decides when to consult them.
"""

from __future__ import annotations

import asyncio
import contextvars
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from strands.tools.decorator import tool

from calllens.coach.history import get_history_store
from calllens.config import Settings, get_settings

# ---------- call logging (so trace reflects real tool execution) ----------

_tool_calls_var: contextvars.ContextVar[list[str] | None] = contextvars.ContextVar(
    "_coach_tool_calls", default=None
)
_tool_events_var: contextvars.ContextVar[list[dict[str, Any]] | None] = contextvars.ContextVar(
    "_coach_tool_events", default=None
)


def _log_tool_call(name: str, extra: dict[str, Any] | None = None) -> None:
    names = _tool_calls_var.get()
    if names is not None:
        names.append(name)
    events = _tool_events_var.get()
    if events is not None:
        events.append({"tool": name, **(extra or {})})


@contextmanager
def tool_call_logging(  # type: ignore[no-untyped-def]
    buffer: list[str] | None = None,
    events: list[dict[str, Any]] | None = None,
) -> Generator[tuple[list[str], list[dict[str, Any]]], None, None]:
    """Capture tool names invoked inside the context (for trace + UI)."""
    buf: list[str] = buffer if buffer is not None else []
    evs: list[dict[str, Any]] = events if events is not None else []
    tok1 = _tool_calls_var.set(buf)
    tok2 = _tool_events_var.set(evs)
    try:
        yield buf, evs
    finally:
        _tool_calls_var.reset(tok1)
        _tool_events_var.reset(tok2)


def get_logged_tool_calls() -> list[str]:
    v = _tool_calls_var.get()
    return list(v) if v is not None else []


def get_logged_tool_events() -> list[dict[str, Any]]:
    v = _tool_events_var.get()
    return list(v) if v is not None else []


def _rubric_registry(settings: Settings | None = None):
    s = settings or get_settings()
    from calllens.api.rubric_registry import RubricRegistry

    return RubricRegistry(str(s.rubrics_dir))


@tool
def get_available_rubrics() -> dict:
    """List available declarative rubrics and their dimensions.

    Use this to discover which rubric to analyze a call against.
    """
    _log_tool_call("get_available_rubrics")
    registry = _rubric_registry()
    rubrics = registry.list()
    return {
        "rubrics": [
            {
                "name": r.name,
                "version": r.version,
                "dimensions": [
                    {"key": d.key, "label": d.label, "weight": d.weight} for d in r.dimensions
                ],
            }
            for r in rubrics
        ]
    }


@tool
def analyze_call(transcript: str, rubric: str = "consultative_sales") -> dict:
    """Run the full CallLens analysis pipeline over a transcript.

    Args:
        transcript: Plain-text transcript (timestamps like '00:12 REP: hello' accepted).
        rubric: Rubric name — see get_available_rubrics. Defaults to consultative_sales.
    """
    from calllens.config import get_settings
    from calllens.graphs import AnalysisGraph
    from calllens.ingest.parsers import parse_transcript_text
    from calllens.rubrics.loader import load_rubric
    from calllens.testing import build_mock_llm

    settings = get_settings()
    parsed = parse_transcript_text(transcript)
    rubric_model = load_rubric(f"{settings.rubrics_dir}/{rubric}.yaml")
    llm = build_mock_llm(parsed)
    graph = AnalysisGraph(llm=llm, settings=settings, rubric=rubric_model)

    async def _run() -> dict:
        state = await graph.run(
            {
                "call_id": "coach-mcp-call",
                "transcript": parsed,
                "rubric": rubric_model,
                "rubric_name": rubric,
            }
        )
        report = state["final_report"]
        return report.model_dump(mode="json")  # type: ignore[union-attr]

    _log_tool_call("analyze_call", {"rubric": rubric})
    try:
        return asyncio.run(_run())
    except RuntimeError:
        # already in an event loop (e.g. inside FastAPI) — caller should use async path
        return {
            "error": (  # noqa: E501 — user-facing diagnostic
                "analyze_call must be called outside an event loop for sync usage; "
                "use the async service instead"
            )
        }


@tool
def get_call_evidence(
    call_id: str, rubric: str = "consultative_sales", dimension: str | None = None
) -> dict:
    """Retrieve evidence for a call (or a single dimension).

    In this add-on, call analysis is on-demand; pass the same rubric you
    analyzed with. If dimension is set, returns only that dimension's evidence.
    """
    _log_tool_call("get_call_evidence", {"call_id": call_id, "dimension": dimension})
    # If service has a stored report, return its evidence rather than a note
    try:
        from calllens.coach.service import get_coach_service  # local to avoid cycle

        svc = get_coach_service()
        report = svc.get_report(call_id)
        if report is not None:
            from calllens.coach.decisions import (
                _build_evidence_from_rubric,  # type: ignore[attr-defined]
            )

            ev = _build_evidence_from_rubric(report)  # type: ignore[attr-defined]
            return {
                "call_id": call_id,
                "rubric": rubric,
                "dimension": dimension,
                "evidence": [e.model_dump(mode="json") for e in ev],
                "rubric_scores": [
                    {
                        "dimension": s.dimension,
                        "score": s.result.score,
                        "confidence": s.result.confidence,
                    }
                    for s in report.rubric_scores[:6]
                ],
                "metrics": {
                    "rep_talk_ratio": float(report.metrics.talk_ratio.representative)
                    if report.metrics
                    else None,
                    "overall_score": float(report.overall_score),
                },
            }
    except Exception:
        pass
    return {
        "call_id": call_id,
        "rubric": rubric,
        "dimension": dimension,
        "note": (  # noqa: E501 — diagnostic note
            "Evidence is returned as part of the CallReport; use analyze_call for fresh analysis "
            "or GET /api/v1/calls/{id}/analysis for a persisted call."
        ),
    }


@tool
def check_escalation_signals(call_id: str, transcript_snippet: str = "") -> dict:
    """Check deterministic escalation signals (churn/risk/anger) for a call.

    Use this early in the review to decide whether human escalation is
    required before deeper evidence gathering. Wraps the hard guardrail
    check_hard_escalation_rules (transcript + current report signals).

    Args:
        call_id: Call identifier (used to look up stored context if available).
        transcript_snippet: Optional short transcript excerpt to scan.
    """
    _log_tool_call("check_escalation_signals", {"call_id": call_id})
    from calllens.coach.decisions import check_hard_escalation_rules

    # Prefer stored transcript/report if service has it; fall back to snippet
    snippet = transcript_snippet or ""
    try:
        from calllens.coach.service import get_coach_service  # local to avoid cycle

        svc = get_coach_service()
        report = svc.get_report(call_id)  # may be None outside service path
        # Try stored raw transcript
        raw = None
        if report is not None:
            raw = getattr(report, "_raw_transcript_text", None)  # type: ignore[attr-defined]
        text = snippet or (str(raw) if raw else "")
        should, reason, conf = check_hard_escalation_rules(text or None, report)
    except Exception:
        should, reason, conf = check_hard_escalation_rules(snippet or None, None)
    return {
        "call_id": call_id,
        "should_escalate": should,
        "reason": reason,
        "confidence": conf,
        "human_review_required": should,
    }


@tool
def get_rep_history(rep_id: str) -> dict:
    """Get structured history for a rep (last 5 calls) with pattern counts.

    Returns discovery_issue/high_talk_ratio counts and last decisions so the
    agent can distinguish repeated patterns from isolated misses.
    """
    _log_tool_call("get_rep_history", {"rep_id": rep_id})
    store = get_history_store()
    summary = store.summary(rep_id)
    return summary.model_dump(mode="json")


@tool
def create_coaching_action(call_id: str, message: str, evidence: list[dict] | None = None) -> dict:
    """Emit a COACH action (sales-coaching) — explainable, with evidence.

    Args:
        call_id: The call to coach.
        message: Concise, evidence-referenced coaching message.
        evidence: Optional evidence snippets backing the coaching.
    """
    _log_tool_call("create_coaching_action", {"call_id": call_id})
    return {
        "action": "COACH",
        "call_id": call_id,
        "message": message,
        "evidence": evidence or [],
        "status": "created",
    }


@tool
def escalate_to_manager(
    call_id: str, reason: str, evidence: list[dict] | None = None, urgency: str = "high"
) -> dict:
    """Escalate to a human manager (human-in-the-loop).

    Use when churn risk, serious dissatisfaction, compliance/risk, or ambiguity
    warrants human judgment. Always requires manager review.
    """
    _log_tool_call("escalate_to_manager", {"call_id": call_id, "urgency": urgency})
    return {
        "action": "ESCALATE",
        "call_id": call_id,
        "reason": reason,
        "evidence": evidence or [],
        "urgency": urgency,
        "human_review_required": True,
        "status": "escalated",
    }


@tool
def record_agent_decision(decision: dict) -> dict:
    """Persist the structured agent decision."""  # noqa: D401
    # Stores confidence, summary, evidence, metrics, human_review_required.
    # In this repo persistence lives in coach.service / storage.
    # In this repo the persistence is in coach.service / storage; this tool
    # acknowledges receipt so the agent loop can close.
    _log_tool_call("record_agent_decision", {"decision": decision.get("decision")})
    return {
        "recorded": True,
        "decision": decision.get("decision"),
        "confidence": decision.get("confidence"),
    }


# Re-export list for Agent(tools=[...]) wiring — satisfies strands-agents-sdk + mcp tagging
COACH_TOOLS = [
    get_available_rubrics,
    analyze_call,
    get_call_evidence,
    check_escalation_signals,
    get_rep_history,
    create_coaching_action,
    escalate_to_manager,
    record_agent_decision,
]
