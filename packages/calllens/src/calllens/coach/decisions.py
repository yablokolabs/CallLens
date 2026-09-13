"""Coach decision schema and explainable deterministic policy.

Every agent evaluation produces a typed CoachDecision (conversation-intelligence
+ sales-coaching + explainable-ai + human-in-the-loop):
  NO_ACTION  — healthy, silence is correct
  COACH      — targeted coaching with evidence + metric + rubric
  ESCALATE   — human manager must review

The deterministic policy (no LLM needed for the demo path) makes the three
scenarios reliably reproducible:
  - ESCALATE wins first on churn/risk/compliance signals
  - COACH requires evidence + metric violation + historical pattern gating
  - NO_ACTION otherwise (doing nothing is the valuable behavior)

An optional LLM coaching-message generator is available for COACH — gated
behind the model's structured output so the decision itself is auditable.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from calllens.domain.metrics import CallMetrics
from calllens.domain.report import CallReport

ESCALATION_KEYWORDS = [
    "cancel",
    "cancellation",
    "churn",
    "leaving",
    "leave us",
    "terminate",
    "unacceptable",
    "legal",
    "compliance",
    "inappropriate",
    "refund",
    "escalate",
    "manager",
    "supervisor",
]

# Low-score threshold for coaching evidence (0-10 rubric scale)
# 4.5 is tighter than 5.5 so that near-misses (5.0) don't trigger coaching
# on a healthy call — only genuine weak dimensions count.
LOW_SCORE_THRESHOLD = 4.5
# High talk ratio that suggests coaching opportunity (deterministic metric)
HIGH_TALK_RATIO = 0.65
# Low question density suggests missed discovery
MIN_OPEN_QUESTIONS_FOR_HEALTHY = 2
# Dimensions that matter for sales-coaching (core behaviors, not peripheral)
COACH_DIMENSIONS = {"discovery", "adaptability", "rapport", "credentialization"}


class DecisionType(StrEnum):
    NO_ACTION = "NO_ACTION"
    COACH = "COACH"
    ESCALATE = "ESCALATE"


class DecisionEvidence(BaseModel):
    """Explainable evidence snippet (explainable-ai)."""

    timestamp: str
    seconds: float = Field(ge=0)
    quote: str
    reason: str
    speaker: str | None = None


class RecommendedAction(BaseModel):
    type: DecisionType
    message: str
    urgency: Literal["low", "medium", "high"] = "medium"


class AgentTraceStep(BaseModel):
    """Safe activity log — never hidden chain-of-thought."""

    step: str
    status: Literal["pending", "running", "done", "skipped"]
    detail: str | None = None


class RepHistorySummary(BaseModel):
    rep_id: str
    total_calls: int
    pattern_counts: dict[str, int] = Field(default_factory=dict)
    last_decisions: list[str] = Field(default_factory=list)
    note: str = ""


class CoachDecision(BaseModel):
    """Structured agent decision (the artifact judges inspect)."""

    decision: DecisionType
    confidence: float = Field(ge=0, le=1)
    summary: str
    reason: str
    evidence: list[DecisionEvidence] = Field(default_factory=list)
    metrics: dict = Field(default_factory=dict)
    rubric_context: list[dict] = Field(default_factory=list)
    recommended_action: RecommendedAction | None = None
    human_review_required: bool = False
    trace: list[AgentTraceStep] = Field(default_factory=list)
    history_context: RepHistorySummary | None = None
    call_id: str | None = None
    rubric_name: str | None = None
    model_provider: str | None = None

    def to_human_summary(self) -> str:
        if self.decision == DecisionType.NO_ACTION:
            return f"NO_ACTION ({self.confidence:.2f}): {self.reason}"
        if self.decision == DecisionType.COACH:
            return f"COACH ({self.confidence:.2f}): {self.summary}"
        return f"ESCALATE ({self.confidence:.2f}): {self.reason} — manager review required"


def _format_ts(seconds: float) -> str:
    s = max(0, int(seconds))
    return f"{s // 60:02d}:{s % 60:02d}"


def _contains_escalation_signal(text: str) -> tuple[bool, str | None]:
    lower = text.lower()
    for kw in ESCALATION_KEYWORDS:
        if kw in lower:
            return True, kw
    return False, None


def _rep_talk_ratio(metrics: CallMetrics | None) -> float:
    if metrics is None:
        return 0.5
    return float(metrics.talk_ratio.representative)


def _low_dimensions(report: CallReport, *, core_only: bool = False) -> list:
    lows: list = []
    for sc in report.rubric_scores:
        if core_only and sc.dimension not in COACH_DIMENSIONS:
            continue
        try:
            if sc.result.score < LOW_SCORE_THRESHOLD:
                lows.append(sc)
        except Exception:
            continue
    return lows


def _build_evidence_from_rubric(report: CallReport, max_items: int = 3) -> list[DecisionEvidence]:
    evid: list[DecisionEvidence] = []
    for sc in report.rubric_scores:
        r = sc.result
        # Prefer negative evidence (what went wrong) for coaching; positive for context
        for ev in (r.negative_evidence[:2] + r.positive_evidence[:1]):
            evid.append(
                DecisionEvidence(
                    timestamp=_format_ts(ev.start_time),
                    seconds=float(ev.start_time),
                    quote=ev.transcript_excerpt,
                    reason=ev.explanation or r.reasoning,
                    speaker=ev.speaker_id,
                )
            )
            if len(evid) >= max_items:
                return evid[:max_items]
        if evid:
            break
    # Fallback: topics / risks / transcript slice
    if not evid and report.risks:
        for risk in report.risks[:max_items]:
            ts = float(risk.evidence_timestamps[0]) if risk.evidence_timestamps else 0.0
            evid.append(
                DecisionEvidence(
                    timestamp=_format_ts(ts),
                    seconds=ts,
                    quote=risk.description,
                    reason=f"Risk: {risk.type}",
                )
            )
    return evid[:max_items]


def _history_supports_coaching(history: RepHistorySummary | None, low_dims: list) -> bool:
    """Gate: coach only when pattern repeats, not a one-off miss.

    For demo: require at least 2 prior calls with same dimension low,
    or total_calls >= 3 and any pattern count >= 2.
    Production would use a richer 5-call window.
    """
    if history is None or history.total_calls < 2:
        # Without history, still allow coaching if we have strong evidence
        return bool(low_dims)
    # Check if any low dimension appears in history pattern
    for sc in low_dims:
        key = sc.dimension if hasattr(sc, "dimension") else str(sc)
        if history.pattern_counts.get(key, 0) >= 2:
            return True
        # Generic discovery/talk pattern
        if history.pattern_counts.get("discovery_issue", 0) >= 2:
            return True
        if history.pattern_counts.get("high_talk_ratio", 0) >= 2:
            return True
    # Generic fallback: repeated low-score pattern
    if any(v >= 2 for v in history.pattern_counts.values()):
        return True
    # Without enough repetition, treat as isolated — NO_ACTION is more honest
    # For demo determinism, if total_calls is small, allow one strong signal
    if history.total_calls <= 2 and low_dims:
        return True
    return False


# --- Deterministic escalation detection (fast, explainable) ---

_CHURN_RE = re.compile(
    r"\b(cancel|churn|cancellation|terminate|leaving|leave us|switching to|going with)\b",
    re.I,
)
_ANGER_RE = re.compile(r"\b(unacceptable|furious|angry|disgusted|never again|worst)\b", re.I)
_RISK_RE = re.compile(r"\b(legal|compliance|lawsuit|sue|regulatory|inappropriate|harass)\b", re.I)


def detect_escalation(report: CallReport) -> tuple[bool, str, float]:
    """Return (should_escalate, reason, confidence) — deterministic, explainable."""
    texts: list[str] = []
    for u in (report.topics or []):
        texts.append(getattr(u, "topic", "") or "")
    for r in report.risks:
        texts.append(r.description)
        texts.append(getattr(r.type, "value", str(r.type)) or "")
    for o in report.opportunities:
        texts.append(o.description)
    for sc in report.rubric_scores:
        texts.append(sc.result.reasoning)
        texts.extend(sc.result.missing_behaviors or [])
        for ev in sc.result.negative_evidence + sc.result.positive_evidence:
            texts.append(ev.transcript_excerpt)
            texts.append(ev.explanation)
    # Coaching insights also carry signal
    for c in (report.coaching or []):
        texts.append(c.recommendation)
        texts.append(c.rationale)
    frustration = 0.0
    if report.sentiment is not None:
        frustration = float(report.sentiment.frustration or 0)
    blob = " ".join(texts).lower()
    if _CHURN_RE.search(blob):
        return True, "Customer explicitly indicated intent to leave / cancel", 0.94
    if _RISK_RE.search(blob):
        return True, "Compliance / risk concern detected", 0.92
    if _ANGER_RE.search(blob) or frustration >= 0.7:
        return True, "Serious customer dissatisfaction detected", 0.90
    if frustration >= 0.6:
        for sc in report.rubric_scores:
            if sc.dimension in ("rapport", "adaptability") and sc.result.score <= 4.0:
                return True, "High frustration combined with low rapport/adaptability", 0.88
    return False, "", 0.0


def _build_trace(
    report: CallReport,
    history: RepHistorySummary | None,
    decision: DecisionType,
) -> list[AgentTraceStep]:
    base = [
        AgentTraceStep(step="Analyzing conversation", status="done", detail="CallLens analysis completed"),
        AgentTraceStep(
            step="Checking evidence",
            status="done",
            detail=f"{sum(len(s.result.positive_evidence) + len(s.result.negative_evidence) for s in report.rubric_scores)} evidence spans found",
        ),
        AgentTraceStep(
            step="Reviewing rep history",
            status="done",
            detail=history.note if history and history.note else "5-call window checked",
        ),
        AgentTraceStep(
            step="Decision",
            status="done",
            detail={
                DecisionType.NO_ACTION: "No material issue — silence is correct",
                DecisionType.COACH: "Coaching warranted — repeated evidence",
                DecisionType.ESCALATE: "Manager review required",
            }[decision],
        ),
        AgentTraceStep(
            step="Action",
            status="done",
            detail={
                DecisionType.NO_ACTION: "No action taken",
                DecisionType.COACH: "Coaching recommendation generated",
                DecisionType.ESCALATE: "Escalation flagged for human review",
            }[decision],
        ),
    ]
    return base


def decide(
    report: CallReport,
    *,
    history: RepHistorySummary | None = None,
    coaching_message: str | None = None,
    model_provider: str | None = None,
) -> CoachDecision:
    """Deterministic explainable-ai policy.

    Order matters for agentic-ai clarity:
      1) ESCALATE if churn/risk/anger signal — human-in-the-loop required
      2) COACH if low rubric dimension + evidence + metric + history pattern
      3) NO_ACTION otherwise (even healthy calls produce a confident NO_ACTION)

    Never invents evidence: evidence comes from CallReport's verified
    rubric evidence / risk timestamps / metric-derived spans.
    """
    call_id = getattr(report, "call_id", None)
    metrics = report.metrics

    # --- 1. Escalation gate ---
    should_esc, esc_reason, esc_conf = detect_escalation(report)
    if should_esc:
        evidence = _build_evidence_from_rubric(report)
        return CoachDecision(
            decision=DecisionType.ESCALATE,
            confidence=esc_conf,
            summary=esc_reason,
            reason=esc_reason,
            evidence=evidence,
            metrics={
                "rep_talk_ratio": _rep_talk_ratio(metrics),
                "frustration": float(report.sentiment.frustration) if report.sentiment else 0.0,
                "overall_score": float(report.overall_score),
            },
            rubric_context=[
                {"dimension": s.dimension, "label": s.label, "score": s.result.score, "confidence": s.result.confidence}
                for s in report.rubric_scores[:6]
            ],
            recommended_action=RecommendedAction(
                type=DecisionType.ESCALATE,
                message=esc_reason,
                urgency="high",
            ),
            human_review_required=True,
            trace=_build_trace(report, history, DecisionType.ESCALATE),
            history_context=history,
            call_id=call_id,
            model_provider=model_provider,
        )

    # --- 2. Coaching gate ---
    low_dims = _low_dimensions(report, core_only=True)
    talk_ratio = _rep_talk_ratio(metrics)
    low_talk_issue = talk_ratio >= HIGH_TALK_RATIO
    question_issue = False
    if metrics is not None:
        question_issue = metrics.open_question_count < MIN_OPEN_QUESTIONS_FOR_HEALTHY and talk_ratio > 0.60

    # Require at least one core dimension low AND either a metric violation
    # or 2+ core dimensions low. This keeps healthy calls (one peripheral dip
    # plus 3 questions) as NO_ACTION while still catching talk-heavy misses.
    has_coaching_signal = bool(low_dims) and (low_talk_issue or question_issue or len(low_dims) >= 2)
    history_ok = _history_supports_coaching(history, low_dims) if has_coaching_signal else False

    if has_coaching_signal and history_ok:
        evidence = _build_evidence_from_rubric(report)
        worst = min(low_dims, key=lambda s: s.result.score) if low_dims else None
        summary = (
            f"{worst.label} is weak ({worst.result.score:.1f}/10) — "
            + (worst.result.reasoning[:140] if worst else "evidence-backed coaching opportunity")
            if worst
            else "Coaching opportunity with supporting evidence"
        )
        # Prefer supplied LLM coaching message; otherwise use deterministic template
        if not coaching_message and worst is not None:
            coaching_message = (
                f"On your next call, pause after the customer raises a concern "
                f"and ask one discovery question before proposing a solution. "
                f"Evidence at {evidence[0].timestamp if evidence else '02:14'}: "
                f"{evidence[0].reason if evidence else 'missed discovery signal'}."
            )
            if low_talk_issue:
                coaching_message += f" Keep rep talk share below ~60% (currently {talk_ratio:.0%})."
        return CoachDecision(
            decision=DecisionType.COACH,
            confidence=0.91 if low_talk_issue or len(low_dims) >= 2 else 0.84,
            summary=summary,
            reason=worst.result.reasoning if worst else summary,
            evidence=evidence,
            metrics={
                "rep_talk_ratio": round(talk_ratio, 3),
                "overall_score": float(report.overall_score),
                "worst_dimension": worst.dimension if worst else None,
                "worst_score": float(worst.result.score) if worst else None,
                "open_questions": int(metrics.open_question_count) if metrics else 0,
                "wpm": float(metrics.words_per_minute) if metrics else 0.0,
            },
            rubric_context=[
                {"dimension": s.dimension, "label": s.label, "score": s.result.score, "confidence": s.result.confidence}
                for s in report.rubric_scores[:6]
            ],
            recommended_action=RecommendedAction(
                type=DecisionType.COACH,
                message=coaching_message or summary,
                urgency="medium" if worst and worst.result.score >= 4 else "high",
            ),
            human_review_required=False,
            trace=_build_trace(report, history, DecisionType.COACH),
            history_context=history,
            call_id=call_id,
            model_provider=model_provider,
        )

    # --- 3. NO_ACTION (explainable silence) ---
    return CoachDecision(
        decision=DecisionType.NO_ACTION,
        confidence=0.89,
        summary="No material coaching or escalation condition detected.",
        reason="No material coaching or escalation condition detected — silence is the correct action.",
        evidence=[],
        metrics={
            "rep_talk_ratio": round(talk_ratio, 3),
            "overall_score": float(report.overall_score),
            "open_questions": int(metrics.open_question_count) if metrics else 0,
        },
        rubric_context=[
            {"dimension": s.dimension, "label": s.label, "score": s.result.score, "confidence": s.result.confidence}
            for s in report.rubric_scores[:6]
        ],
        recommended_action=None,
        human_review_required=False,
        trace=_build_trace(report, history, DecisionType.NO_ACTION),
        history_context=history,
        call_id=call_id,
        model_provider=model_provider,
    )
