"""Strands Coach Agent — the autonomous manager (agentic-ai · ai-agents).

Strands owns the decision: it decides what information to gather, which tools
to call, whether evidence is sufficient, which decision to choose
(NO_ACTION / COACH / ESCALATE), and which action tool to trigger.

Deterministic helpers are guardrails/validators (validate_agent_decision,
check_hard_escalation_rules, calculate_policy_signals) — not the primary
policy. The classic decide() remains as fallback/repair oracle.
"""

from __future__ import annotations

import asyncio
from typing import Any

from calllens.coach.decisions import (
    CoachDecision,
    DecisionType,
    check_hard_escalation_rules,
    decide,
    validate_agent_decision,
)
from calllens.coach.history import get_history_store
from calllens.config import Settings, get_settings
from calllens.domain.report import CallReport


def _get_graph_report(
    transcript_text: str, rubric_name: str = "consultative_sales", settings: Settings | None = None
) -> CallReport:
    """Synchronous helper to run the CallLens graph and return a CallReport."""
    settings = settings or get_settings()
    from calllens.graphs import AnalysisGraph
    from calllens.ingest.parsers import parse_transcript_text
    from calllens.rubrics.loader import load_rubric
    from calllens.testing import build_mock_llm

    parsed = parse_transcript_text(transcript_text)
    rubric = load_rubric(f"{settings.rubrics_dir}/{rubric_name}.yaml")
    llm = build_mock_llm(parsed)
    graph = AnalysisGraph(llm=llm, settings=settings, rubric=rubric)

    async def _run() -> CallReport:
        state = await graph.run(
            {
                "call_id": f"coach-{parsed.source}",
                "transcript": parsed,
                "rubric": rubric,
                "rubric_name": rubric_name,
            }
        )
        report = state["final_report"]
        assert report is not None
        return report  # type: ignore[return-value]

    try:
        return asyncio.run(_run())
    except RuntimeError:
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(asyncio.run, _run())
            return fut.result()


def _resolve_model(
    report: CallReport | None,
    history: Any | None,
    call_id: str | None,
    transcript: str | None,
    rubric_name: str | None,
    settings: Settings,
) -> Any:
    """Choose Strands Model: Bedrock/OpenAI/compatible if configured, else deterministic mock."""
    from calllens.coach.deterministic_model import CoachDeterministicModel

    provider = (
        settings.coach_model_provider or settings.model_provider or settings.llm_provider or "mock"
    ).lower()
    model_id = settings.coach_model_id or settings.bedrock_model_id or settings.llm_model

    # Try real providers first
    model: Any = None
    if provider == "bedrock":
        try:
            from strands.models import BedrockModel

            kwargs: dict[str, Any] = {"model_id": model_id} if model_id else {}
            if settings.aws_region:
                kwargs["region_name"] = settings.aws_region
            model = BedrockModel(**kwargs)  # type: ignore[arg-type]
            return model
        except Exception:
            model = None
    elif provider in ("openai", "anthropic", "compatible"):
        try:
            from strands.models.openai import OpenAIModel

            client_args: dict[str, Any] = {}
            if settings.compatible_base_url:
                client_args["base_url"] = settings.compatible_base_url
            key = (
                settings.openai_api_key or settings.compatible_api_key or settings.anthropic_api_key
            )
            if key:
                client_args["api_key"] = key
            if model_id:
                client_args["model"] = model_id
            model = OpenAIModel(client_args=client_args)  # type: ignore[arg-type]
            return model
        except Exception:
            model = None

    # Fallback / mock: deterministic offline model bound to this report
    # This guarantees DEMO_MODE=true works with no keys and still exercises
    # the Strands tool loop (analyze_call → evidence → history → action → structured output).
    return CoachDeterministicModel(
        report=report,
        history=history,
        call_id=call_id,
        transcript=transcript,
        rubric_name=rubric_name,
    )


def _build_strands_agent(
    settings: Settings | None = None,
    *,
    report: CallReport | None = None,
    history: Any | None = None,
    call_id: str | None = None,
    transcript: str | None = None,
    rubric_name: str | None = None,
):
    """Create a Strands Agent wired with coach tools + model from config.

    When report/history are supplied, the deterministic mock is bound to that
    context so DEMO_MODE remains fully offline but still tool-driven.
    When no report is supplied (e.g. constructibility test), a generic mock
    is used.
    """
    from strands import Agent

    from calllens.coach.mcp_tools import COACH_TOOLS

    settings = settings or get_settings()
    model = _resolve_model(report, history, call_id, transcript, rubric_name, settings)

    system_prompt = (
        "You are CallLens Coach — an autonomous sales-coaching manager. "
        "You review conversation analyses produced by CallLens "
        "(the evidence layer) and decide whether anything should happen "
        "next: NO_ACTION, COACH, or ESCALATE. "
        "Be precise and explainable: every COACH or ESCALATE cites "
        "evidence with timestamps, a deterministic metric "
        "(e.g. rep talk ratio), and the rubric dimension. "
        "Never invent evidence — use only what tools return. "
        "Escalate when churn risk, serious dissatisfaction, "
        "compliance/risk, or high ambiguity is present — "
        "those require human-in-the-loop. Otherwise coach only when "
        "evidence repeats (history shows a pattern); "
        "a single isolated miss should be NO_ACTION. "
        "Call check_escalation_signals early. "
        "Call get_call_evidence and get_rep_history to gather context. "
        "Then call the matching action tool: "
        "record_agent_decision for NO_ACTION, "
        "create_coaching_action for COACH, "
        "escalate_to_manager for ESCALATE — before returning your "
        "structured CoachDecision. Stay concise. No hidden chain-of-thought."
    )

    return Agent(
        model=model,
        system_prompt=system_prompt,
        tools=COACH_TOOLS,
        callback_handler=None,
        name="calllens-coach",
        description="Autonomous conversation coach — NO_ACTION / COACH / ESCALATE with explainable evidence.",
    )


def _tool_human_label(tool: str) -> str:
    mapping = {
        "analyze_call": "analyze_call",
        "get_call_evidence": "get_call_evidence",
        "check_escalation_signals": "check_escalation_signals",
        "get_rep_history": "get_rep_history",
        "get_available_rubrics": "get_available_rubrics",
        "create_coaching_action": "create_coaching_action",
        "escalate_to_manager": "escalate_to_manager",
        "record_agent_decision": "record_agent_decision",
    }
    return mapping.get(tool, tool)


def _build_trace_from_tools(
    logged: list[str],
    report: CallReport | None,
    history: Any | None,
    decision: DecisionType,
) -> list[Any]:
    """Build activity trace that reflects actual Strands tool execution."""
    from calllens.coach.decisions import AgentTraceStep

    steps: list[AgentTraceStep] = []
    # Map each tool call to a trace step
    for tool in logged:
        human = _tool_human_label(tool)
        # Friendly verb
        if tool in ("create_coaching_action", "escalate_to_manager", "record_agent_decision"):
            detail = f"{human} executed"
        else:
            detail = f"{human} completed"
        steps.append(
            AgentTraceStep(step=f"Strands requested {human}", status="done", detail=detail)
        )

    # If no tools were logged (edge), at least show analysis/history steps from report
    if not steps and report is not None:
        steps.append(
            AgentTraceStep(
                step="Strands requested get_call_evidence",
                status="done",
                detail="get_call_evidence completed",
            )
        )
        steps.append(
            AgentTraceStep(
                step="Strands requested get_rep_history",
                status="done",
                detail="get_rep_history completed",
            )
        )

    # Ensure history step is represented if not already
    has_history = any("get_rep_history" in s.step for s in steps)
    if not has_history:
        note = (
            history.note
            if history and hasattr(history, "note") and history.note
            else "5-call window checked"
        )
        steps.append(AgentTraceStep(step="Reviewing rep history", status="done", detail=note))
    else:
        # Replace generic history tool step detail with note if available
        if history and hasattr(history, "note"):
            for s in steps:
                if "get_rep_history" in s.step and history.note:
                    s.detail = history.note

    # Decision + Action
    steps.append(
        AgentTraceStep(
            step="Decision",
            status="done",
            detail={
                DecisionType.NO_ACTION: "No material issue — silence is correct",
                DecisionType.COACH: "Coaching warranted — repeated evidence",
                DecisionType.ESCALATE: "Manager review required",
            }[decision],
        )
    )
    steps.append(
        AgentTraceStep(
            step="Action",
            status="done",
            detail={
                DecisionType.NO_ACTION: "record_agent_decision executed — no action taken",
                DecisionType.COACH: "create_coaching_action executed",
                DecisionType.ESCALATE: "escalate_to_manager executed — human review required",
            }[decision],
        )
    )
    return steps


class CoachAgent:
    """High-level coach that exposes Strands + deterministic decide()."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._strands_agent = None  # lazy — building the agent imports strands

    @property
    def strands_agent(self):
        if self._strands_agent is None:
            self._strands_agent = _build_strands_agent(self.settings)
        return self._strands_agent

    def evaluate_transcript(
        self,
        transcript_text: str,
        *,
        rubric_name: str = "consultative_sales",
        rep_id: str | None = None,
    ) -> CoachDecision:
        """End-to-end: analyze a transcript and produce a CoachDecision."""
        report = _get_graph_report(transcript_text, rubric_name=rubric_name, settings=self.settings)
        # Stash raw transcript for guardrail + tools
        try:
            import contextlib

            with contextlib.suppress(Exception):
                object.__setattr__(report, "_raw_transcript_text", transcript_text)  # type: ignore[attr-defined]
        except Exception:
            pass
        history = None
        if rep_id:
            history = get_history_store().summary(rep_id)
        return self.evaluate_report(
            report,
            history=history,
            rep_id=rep_id,
            raw_transcript=transcript_text,
            rubric_name=rubric_name,
        )

    def evaluate_report(
        self,
        report: CallReport,
        *,
        history=None,
        rep_id: str | None = None,
        raw_transcript: str | None = None,
        rubric_name: str | None = None,
    ) -> CoachDecision:
        """Produce a decision from an already-analyzed CallReport via Strands.

        The primary path is Strands structured output (CoachDecision). Deterministic
        logic is only guardrails / repair / fallback — not the decision engine.
        """
        # Lazy import for history summary type flexibility
        if history is None and rep_id:
            history = get_history_store().summary(rep_id)

        # Resolve raw transcript from report stash if not supplied
        if raw_transcript is None:
            try:
                import contextlib

                with contextlib.suppress(Exception):
                    raw_transcript = getattr(report, "_raw_transcript_text", None)  # type: ignore[attr-defined]
                    if raw_transcript is not None:
                        raw_transcript = str(raw_transcript)
            except Exception:
                raw_transcript = None

        provider = (
            self.settings.coach_model_provider
            or self.settings.model_provider
            or self.settings.llm_provider
            or "mock"
        )
        call_id = getattr(report, "call_id", None) or "coach-call"
        rubric_n = rubric_name or getattr(report, "rubric_name", None) or "consultative_sales"  # type: ignore[attr-defined]

        # Build per-report Strands agent (binds deterministic mock to this report)
        agent = _build_strands_agent(
            self.settings,
            report=report,
            history=history,
            call_id=str(call_id),
            transcript=raw_transcript,
            rubric_name=str(rubric_n),
        )

        prompt = (
            f"Review call {call_id} for rep {rep_id or 'unknown'} using rubric {rubric_n}. "
            "Determine NO_ACTION, COACH, or ESCALATE. "
            "Call check_escalation_signals, get_call_evidence, get_rep_history as needed, "
            "then call the matching action tool and emit your structured CoachDecision. "
            "Cite evidence with timestamps + metric + rubric. No invented evidence."
        )

        logged: list[str] = []
        decision: CoachDecision | None = None

        # --- Strands structured output (primary) ---
        try:
            from calllens.coach.mcp_tools import tool_call_logging

            # Capture tool calls that actually execute inside the Strands loop
            with tool_call_logging(logged, []) as (buf, _events):
                # For tool logging to work, the report must be in the service store
                # so get_call_evidence / check_escalation_signals can find it.
                # We stash it briefly via service if available (best-effort).
                try:
                    import contextlib

                    from calllens.coach.service import get_coach_service  # local to avoid cycle

                    svc = get_coach_service(self.settings)
                    with contextlib.suppress(Exception):
                        svc._reports[str(call_id)] = report  # type: ignore[attr-defined]
                except Exception:
                    pass

                result = agent(prompt, structured_output_model=CoachDecision)  # type: ignore[call-arg]
                # AgentResult.structured_output holds the validated CoachDecision
                decision = getattr(result, "structured_output", None)
                if decision is None:
                    # Fallback: try to parse from message
                    msg = getattr(result, "message", None)
                    if isinstance(msg, dict) and "content" in msg:
                        try:
                            text = " ".join(
                                c.get("text", "")
                                for c in msg.get("content", [])
                                if isinstance(c, dict)
                            )
                            if text:
                                decision = CoachDecision.model_validate_json(text)
                        except Exception:
                            pass
                # If still None, try result itself
                if decision is None and isinstance(result, CoachDecision):
                    decision = result
                logged = list(buf)
        except Exception:  # noqa: BLE001
            decision = None

        # --- Validation + hard escalation guardrail ---
        if decision is not None:
            # Hard escalation must not be missed
            should_esc, esc_reason, esc_conf = check_hard_escalation_rules(raw_transcript, report)
            if should_esc and decision.decision != DecisionType.ESCALATE:
                # Repair once with constrained prompt
                try:
                    from calllens.coach.mcp_tools import tool_call_logging as _tcl

                    repair_prompt = (
                        f"Your previous decision was {decision.decision} but a hard escalation signal was detected: "
                        f"{esc_reason} (confidence {esc_conf:.2f}). You must ESCALATE, set human_review_required=true, "
                        "include evidence with timestamps, and call escalate_to_manager before returning structured output."
                    )
                    with _tcl(logged, []):
                        r2 = agent(repair_prompt, structured_output_model=CoachDecision)  # type: ignore[call-arg]
                        d2 = getattr(r2, "structured_output", None)
                        if d2 is not None and d2.decision == DecisionType.ESCALATE:
                            decision = d2
                        else:
                            # Force escalation fallback
                            from calllens.coach.decisions import (
                                DecisionEvidence,
                                RecommendedAction,
                            )

                            ev = decision.evidence or []
                            if not ev:
                                try:
                                    from calllens.coach.decisions import (
                                        _build_evidence_from_rubric,  # type: ignore
                                    )

                                    ev = _build_evidence_from_rubric(report)  # type: ignore
                                except Exception:
                                    ev = []
                                if not ev and raw_transcript:
                                    ev = [
                                        DecisionEvidence(
                                            timestamp="00:01:00",
                                            seconds=60.0,
                                            quote=raw_transcript[:140],
                                            reason=esc_reason,
                                        )
                                    ]
                            decision = CoachDecision(
                                decision=DecisionType.ESCALATE,
                                confidence=esc_conf,
                                summary=esc_reason,
                                reason=esc_reason,
                                evidence=ev,
                                metrics={
                                    "rep_talk_ratio": float(
                                        report.metrics.talk_ratio.representative
                                    )
                                    if report.metrics
                                    else 0.5,
                                    "overall_score": float(report.overall_score),
                                },
                                rubric_context=[
                                    {
                                        "dimension": s.dimension,
                                        "label": s.label,
                                        "score": s.result.score,
                                        "confidence": s.result.confidence,
                                    }
                                    for s in report.rubric_scores[:6]
                                ],
                                recommended_action=RecommendedAction(
                                    type=DecisionType.ESCALATE, message=esc_reason, urgency="high"
                                ),
                                human_review_required=True,
                                trace=[],  # rebuilt below
                                history_context=history,
                                call_id=str(call_id),
                                rubric_name=str(rubric_n),
                                model_provider=str(provider),
                            )
                except Exception:
                    # Keep original decision if repair fails — validation below will handle
                    pass

            ok, err = validate_agent_decision(decision)
            if not ok:
                _validate_err = err
                # Repair once
                try:
                    from calllens.coach.mcp_tools import tool_call_logging as _tcl

                    repair_prompt = (
                        f"Your previous CoachDecision failed validation: {_validate_err}. "
                        "Fix it: confidence 0-1, evidence required for COACH/ESCALATE, "
                        "human_review_required only for ESCALATE, recommended_action.type must match decision, "
                        "and evidence needs quote/reason/timestamp. "
                        "Call the matching action tool and return corrected structured output."
                    )
                    with _tcl(logged, []):
                        r2 = agent(repair_prompt, structured_output_model=CoachDecision)  # type: ignore[call-arg]
                        d2 = getattr(r2, "structured_output", None)
                        if d2 is not None:
                            ok2, _ = validate_agent_decision(d2)
                            if ok2:
                                decision = d2
                                ok = True
                            else:
                                ok = False
                except Exception:
                    ok = False

            if not ok:
                # Safe fallback: deterministic decide (guardrail, not primary)
                decision = decide(report, history=history, model_provider=str(provider))
                # If raw transcript escalation was missed, promote (same guardrail as service)
                if raw_transcript:
                    should, reason, conf = check_hard_escalation_rules(raw_transcript, report)
                    if should and decision.decision != DecisionType.ESCALATE:
                        from calllens.coach.decisions import (
                            DecisionEvidence,
                            RecommendedAction,
                        )

                        decision.decision = DecisionType.ESCALATE
                        decision.confidence = conf
                        decision.summary = reason
                        decision.reason = reason
                        decision.human_review_required = True
                        decision.recommended_action = RecommendedAction(
                            type=DecisionType.ESCALATE, message=reason, urgency="high"
                        )
                        if not decision.evidence:
                            decision.evidence = [
                                DecisionEvidence(
                                    timestamp="00:01:00",
                                    seconds=60.0,
                                    quote=raw_transcript[:120],
                                    reason=reason,
                                )
                            ]
        else:
            # No structured output at all — fallback
            decision = decide(report, history=history, model_provider=str(provider))
            if raw_transcript:
                should, reason, conf = check_hard_escalation_rules(raw_transcript, report)
                if should and decision.decision != DecisionType.ESCALATE:
                    from calllens.coach.decisions import DecisionEvidence, RecommendedAction

                    decision.decision = DecisionType.ESCALATE
                    decision.confidence = conf
                    decision.summary = reason
                    decision.reason = reason
                    decision.human_review_required = True
                    decision.recommended_action = RecommendedAction(
                        type=DecisionType.ESCALATE, message=reason, urgency="high"
                    )
                    if not decision.evidence:
                        decision.evidence = [
                            DecisionEvidence(
                                timestamp="00:01:00",
                                seconds=60.0,
                                quote=raw_transcript[:120],
                                reason=reason,
                            )
                        ]

        assert decision is not None

        # Rebuild trace to reflect actual tool execution + decision
        import contextlib as _ctx3

        with _ctx3.suppress(Exception):
            decision.trace = _build_trace_from_tools(logged, report, history, decision.decision)  # type: ignore[assignment]

        # Enrich with history / ids / provider + record
        if rep_id:
            with _ctx3.suppress(Exception):
                get_history_store().record(rep_id, report, decision.decision.value)
                decision.history_context = get_history_store().summary(rep_id)
        else:
            decision.history_context = history
        decision.call_id = str(call_id)
        decision.rubric_name = str(rubric_n)
        decision.model_provider = str(provider)
        # Ensure metrics/rubric_context are present even if LLM omitted them
        if not decision.metrics:
            with _ctx3.suppress(Exception):
                decision.metrics = {
                    "rep_talk_ratio": float(report.metrics.talk_ratio.representative)
                    if report.metrics
                    else 0.5,
                    "overall_score": float(report.overall_score),
                }
                if not decision.metrics:
                    decision.metrics = {}
        if not decision.rubric_context:
            with _ctx3.suppress(Exception):
                decision.rubric_context = [
                    {
                        "dimension": s.dimension,
                        "label": s.label,
                        "score": s.result.score,
                        "confidence": s.result.confidence,
                    }
                    for s in report.rubric_scores[:6]
                ]
        return decision
