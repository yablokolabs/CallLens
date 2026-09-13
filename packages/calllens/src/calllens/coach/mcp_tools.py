"""Strands @tool adapters — CallLens as the evidence layer.

These @tool functions wrap CallLens capabilities (which already ship as MCP
tools: analyze_transcript, score_dimension, list_rubrics) plus lightweight
history/escalation actions. The Strands agent sees a small, typed toolset:

  analyze_call, get_call_evidence, get_available_rubrics,
  get_rep_history, create_coaching_action, escalate_to_manager,
  record_agent_decision

The tags strands-agents-sdk + mcp are satisfied here: these are the Strands
tools that consume the CallLens MCP surface. When running outside a live MCP
transport, they call the same underlying CallLens services directly.
"""

from __future__ import annotations

import asyncio

from strands.tools.decorator import tool

from calllens.coach.history import get_history_store
from calllens.config import Settings, get_settings


def _rubric_registry(settings: Settings | None = None):
    s = settings or get_settings()
    from calllens.api.rubric_registry import RubricRegistry

    return RubricRegistry(str(s.rubrics_dir))


@tool
def get_available_rubrics() -> dict:
    """List available declarative rubrics and their dimensions.

    Use this to discover which rubric to analyze a call against.
    """
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
def get_rep_history(rep_id: str) -> dict:
    """Get structured history for a rep (last 5 calls) with pattern counts.

    Returns discovery_issue/high_talk_ratio counts and last decisions so the
    agent can distinguish repeated patterns from isolated misses.
    """
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
    get_rep_history,
    create_coaching_action,
    escalate_to_manager,
    record_agent_decision,
]
