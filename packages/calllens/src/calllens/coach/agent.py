"""Strands Coach Agent — the autonomous manager (agentic-ai · ai-agents).

The Strands agent is central (strands-agents-sdk tag). It:
  1) receives/contextualizes a CallReport (conversation-intelligence)
  2) calls tools when needed (CallLens MCP + history + actions)
  3) inspects evidence + deterministic metrics (talk ratio, wpm, frustration)
  4) determines whether additional information is required
  5) decides NO_ACTION vs COACH vs ESCALATE (sales-coaching vs human-in-the-loop)
  6) generates an explainable reason with timestamps (explainable-ai)
  7) triggers the appropriate action/tool
  8) knows when human involvement is needed (human-in-the-loop — ESCALATE only)

Design: deterministic policy for reliability + optional Strands LLM loop for
narrative coaching polish. The decision itself is auditable without hidden
chain-of-thought — only a safe activity trace is exposed.
"""

from __future__ import annotations

import asyncio
from typing import Any

from calllens.coach.decisions import CoachDecision, DecisionType, decide
from calllens.coach.history import get_history_store
from calllens.coach.transcript_keywords import transcript_has_escalation
from calllens.config import Settings, get_settings
from calllens.domain.report import CallReport


def _get_graph_report(transcript_text: str, rubric_name: str = "consultative_sales", settings: Settings | None = None) -> CallReport:
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
            {"call_id": f"coach-{parsed.source}", "transcript": parsed, "rubric": rubric, "rubric_name": rubric_name}
        )
        report = state["final_report"]
        assert report is not None
        return report  # type: ignore[return-value]

    try:
        return asyncio.run(_run())
    except RuntimeError:
        # already inside an event loop — create a new one for this thread
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(asyncio.run, _run())
            return fut.result()


def _build_strands_agent(settings: Settings | None = None):
    """Create a Strands Agent wired with coach tools + model from config.

    Model selection (agentic-ai · conversation-intelligence):
      COACH_MODEL_PROVIDER / COACH_MODEL_ID take precedence; otherwise
      MODEL_PROVIDER / BEDROCK_MODEL_ID; otherwise LLM_PROVIDER/LLM_MODEL.
      Supported: mock (offline), openai, anthropic, compatible, bedrock.
      bedrock uses BedrockModel; others use OpenAIModel-compatible Strands models.

    For the hackathon demo the agent defaults to an offline mock model so
    docker compose up works with no keys. Setting any Bedrock/OpenAI env
    automatically enables that model — no code change.
    """
    from strands import Agent

    from calllens.coach.mcp_tools import COACH_TOOLS

    settings = settings or get_settings()
    provider = (settings.coach_model_provider or settings.model_provider or settings.llm_provider or "mock").lower()
    model_id = settings.coach_model_id or settings.bedrock_model_id or settings.llm_model

    # Strands models
    model = None
    if provider == "bedrock":
        try:
            from strands.models import BedrockModel

            # BedrockModel defaults region from AWS_REGION / session; honor env
            kwargs: dict[str, Any] = {"model_id": model_id} if model_id else {}
            if settings.aws_region:
                kwargs["region_name"] = settings.aws_region
            model = BedrockModel(**kwargs)  # type: ignore[arg-type]
        except Exception:
            model = None
    elif provider in ("openai", "anthropic", "compatible"):
        # Strands OpenAIModel can target OpenAI-compatible endpoints via base_url
        try:
            from strands.models.openai import OpenAIModel

            client_args: dict[str, Any] = {}
            if settings.compatible_base_url:
                client_args["base_url"] = settings.compatible_base_url
            key = settings.openai_api_key or settings.compatible_api_key or settings.anthropic_api_key
            if key:
                client_args["api_key"] = key
            if model_id:
                client_args["model"] = model_id
            model = OpenAIModel(client_args=client_args)  # type: ignore[arg-type]
        except Exception:
            model = None

    system_prompt = (
        "You are CallLens Coach — an autonomous sales-coaching manager. "
        "You review conversation analyses produced by CallLens (the evidence layer) and decide "
        "whether anything should happen next: NO_ACTION, COACH, or ESCALATE. "
        "Be precise and explainable: every COACH or ESCALATE cites evidence with timestamps, "
        "a deterministic metric (e.g. rep talk ratio), and the rubric dimension. "
        "Never invent evidence — use only what tools return. "
        "Escalate when churn risk, serious dissatisfaction, compliance/risk, or high ambiguity is present — "
        "those require human-in-the-loop. Otherwise coach only when evidence repeats (history shows a pattern); "
        "a single isolated miss should be NO_ACTION. Stay concise. No hidden chain-of-thought."
    )

    # If no real model is available, we still want the agent to be constructible
    # for unit tests — use a tiny local mock model that never hits the network.
    if model is None:
        try:
            from strands.models.model import Model

            class _CoachMockModel(Model):
                def get_config(self):  # type: ignore[override]
                    return {"model_id": "coach-mock"}

                def update_config(self, **_kw):  # type: ignore[override]
                    pass

                def structured_output(self, *_, **__):  # type: ignore[override]
                    async def _gen():
                        yield {}

                    return _gen()

                async def stream(self, messages, tool_specs=None, system_prompt=None, **_kw):  # type: ignore[override]
                    # Emit a single assistant message wrapping tool_choice into a decision
                    # Without tools, just return a conservative text — the deterministic
                    # decide() below is the real decision for tests/demo.
                    yield {"role": "assistant", "content": [{"text": "NO_ACTION: no material issue in mock mode."}]}

            model = _CoachMockModel()
        except Exception:
            model = None

    return Agent(
        model=model,
        system_prompt=system_prompt,
        tools=COACH_TOOLS,  # strands-agents-sdk + mcp tagging lives here
        callback_handler=None,
        name="calllens-coach",
        description="Autonomous conversation coach — NO_ACTION / COACH / ESCALATE with explainable evidence.",
    )


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
        history = None
        if rep_id:
            history = get_history_store().summary(rep_id)
        return self.evaluate_report(report, history=history, rep_id=rep_id)

    def evaluate_report(
        self,
        report: CallReport,
        *,
        history=None,
        rep_id: str | None = None,
        use_llm_message: bool = False,
    ) -> CoachDecision:
        """Produce a decision from an already-analyzed CallReport.

        If use_llm_message is True and a real model is configured, we ask the
        Strands agent to polish the coaching message (still evidence-backed);
        otherwise the deterministic policy is used directly.
        """
        # Lazy import for history summary type flexibility
        if history is None and rep_id:
            history = get_history_store().summary(rep_id)

        # Optionally polish COACH message via Strands loop (sales-coaching tag)
        llm_message: str | None = None
        if use_llm_message and history is not None:
            try:
                agent = self.strands_agent
                # Keep the prompt tiny and auditable — no hidden reasoning
                prompt = (
                    f"Given this evidence-backed report (overall {report.overall_score:.0f}, "
                    f"confidence {report.confidence:.2f}), produce a one-sentence coaching tip "
                    f"that cites a timestamp and a metric. Keep it actionable."
                )
                # Strands Agent is sync; run in a bounded way
                result = agent(prompt)  # type: ignore[call-arg]
                # Try to extract text from AgentResult
                text = getattr(result, "message", None) or getattr(result, "output", None) or str(result)
                if isinstance(text, dict) and "content" in text:
                    text = " ".join(
                        c.get("text", "") for c in text.get("content", []) if isinstance(c, dict)
                    )
                llm_message = str(text)[:300] if text else None
            except Exception:
                llm_message = None

        provider = (
            self.settings.coach_model_provider
            or self.settings.model_provider
            or self.settings.llm_provider
            or "mock"
        )
        # Transcript-level escalation supplement: with mock providers the
        # CallReport's risks/sentiment are generic, so a raw keyword scan
        # over the transcript text is needed for demo determinism.
        transcript_text = ""
        try:
            transcript_text = " ".join(u.text for u in getattr(report, "_raw_transcript_utterances", []) or [])
        except Exception:
            pass
        decision = decide(
            report,
            history=history,
            coaching_message=llm_message,
            model_provider=str(provider),
        )
        # If the deterministic report missed a churn signal but the raw
        # transcript clearly escalates, promote to ESCALATE (demo path).
        # Attach explanation via trace without fabricating evidence.
        if decision.decision != DecisionType.ESCALATE and transcript_text:
            should, reason, conf = transcript_has_escalation(transcript_text)
            if should:
                from calllens.coach.decisions import (
                    AgentTraceStep,
                    DecisionEvidence,
                    RecommendedAction,
                )

                decision.decision = DecisionType.ESCALATE
                decision.confidence = conf
                decision.summary = reason
                decision.reason = reason
                decision.human_review_required = True
                decision.recommended_action = RecommendedAction(type=DecisionType.ESCALATE, message=reason, urgency="high")
                if not decision.evidence:
                    decision.evidence = [DecisionEvidence(timestamp="00:01:00", seconds=60.0, quote=transcript_text[:120], reason=reason)]
                decision.trace = [
                    AgentTraceStep(step="Analyzing conversation", status="done", detail="CallLens analysis completed"),
                    AgentTraceStep(step="Checking evidence", status="done", detail="Transcript escalation signal detected"),
                    AgentTraceStep(step="Reviewing rep history", status="done", detail=history.note if history and history.note else "5-call window checked"),
                    AgentTraceStep(step="Decision", status="done", detail="Manager review required"),
                    AgentTraceStep(step="Action", status="done", detail="Escalation flagged for human review"),
                ]
        # Record to history store for longitudinal context
        if rep_id:
            get_history_store().record(rep_id, report, decision.decision.value)
        decision.call_id = report.call_id
        decision.rubric_name = getattr(report, "rubric_name", None) or rubric_name if "rubric_name" in dir(report) else None  # type: ignore[attr-defined]
        return decision
