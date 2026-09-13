"""Deterministic Strands model for offline demo (no network, no keys).

Implements strands.models.Model so the Coach Agent's tool loop is genuine:
  report → Strands tool calls → structured CoachDecision → action tool

The model is *bound* to a specific CallReport + history at construction time,
so its tool-selection is deterministic and reproducible for the three demo
scenarios (NO_ACTION / COACH / ESCALATE). It does NOT call any LLM.

This keeps DEMO_MODE=true fully offline while still proving:
  Strands → tool calls → structured decision → action tool
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from strands.models.model import Model

from calllens.coach.decisions import CoachDecision


class CoachDeterministicModel(Model):
    """Strands Model that deterministically drives the Coach tool loop."""

    def __init__(
        self,
        *,
        report: Any | None = None,
        history: Any | None = None,
        call_id: str | None = None,
        transcript: str | None = None,
        rubric_name: str | None = None,
    ) -> None:
        self._report = report
        self._history = history
        self._call_id = call_id or (getattr(report, "call_id", None) if report else "coach-call")
        self._transcript = transcript or ""
        self._rubric_name = rubric_name or "consultative_sales"
        self._turn = 0
        # Pre-compute expected decision for structured output (uses same
        # deterministic policy the guardrails validate — not LLM reasoning).
        self._precomputed: CoachDecision | None = None
        try:
            if report is not None:
                from calllens.coach.decisions import decide

                # Use history if provided; keep provider as mock
                self._precomputed = decide(report, history=history, model_provider="mock")
                # Transcript-level escalation supplement (matches service logic)
                if self._precomputed.decision.value != "ESCALATE" and transcript:
                    from calllens.coach.decisions import (
                        DecisionEvidence,
                        DecisionType,
                        RecommendedAction,
                    )
                    from calllens.coach.transcript_keywords import transcript_has_escalation

                    should, reason, conf = transcript_has_escalation(transcript)
                    if should:
                        self._precomputed.decision = DecisionType.ESCALATE  # type: ignore[assignment]
                        self._precomputed.confidence = conf
                        self._precomputed.summary = reason
                        self._precomputed.reason = reason
                        self._precomputed.human_review_required = True
                        self._precomputed.recommended_action = RecommendedAction(
                            type=DecisionType.ESCALATE, message=reason, urgency="high"
                        )
                        if not self._precomputed.evidence:
                            self._precomputed.evidence = [
                                DecisionEvidence(
                                    timestamp="00:01:00",
                                    seconds=60.0,
                                    quote=(transcript[:140] if transcript else reason),
                                    reason=reason,
                                )
                            ]
        except Exception:
            self._precomputed = None

    def get_config(self) -> Any:  # type: ignore[override]
        return {"model_id": "coach-deterministic-mock"}

    def update_config(self, **_kw: Any) -> None:  # type: ignore[override]
        pass

    async def structured_output(  # type: ignore[override]
        self,
        output_model: type[CoachDecision],
        prompt: Any,
        system_prompt: str | None = None,
        **_kw: Any,
    ):  # type: ignore[no-untyped-def]
        """Direct structured_output path (not the agent loop) — return precomputed."""

        async def _gen():  # type: ignore[no-untyped-def]
            if self._precomputed is not None and issubclass(output_model, CoachDecision):
                # Ensure model_provider reflects deterministic mock
                import contextlib as _ctx

                with _ctx.suppress(Exception):
                    self._precomputed.model_provider = "mock"  # type: ignore[attr-defined]
                yield {"output": self._precomputed}
            else:
                # Fallback minimal
                from calllens.coach.decisions import DecisionType

                fallback = CoachDecision(
                    decision=DecisionType.NO_ACTION,  # type: ignore[arg-type]
                    confidence=0.89,
                    summary="No material issue (deterministic mock).",
                    reason="No material coaching or escalation condition detected.",
                )
                yield {"output": fallback}

        return _gen()

    async def stream(  # type: ignore[override]
        self,
        messages: Any,
        tool_specs: list[dict[str, Any]] | None = None,
        system_prompt: str | None = None,
        *,
        tool_choice: Any | None = None,
        system_prompt_content: Any | None = None,
        invocation_state: dict[str, Any] | None = None,
        cancel_signal: Any | None = None,
        **_kw: Any,
    ):  # type: ignore[no-untyped-def]
        """Deterministic tool loop.

        Without structured_output_model (normal path):
          turn 0: check_escalation_signals + get_call_evidence + get_rep_history
          turn 1: create_coaching_action / escalate_to_manager / record_agent_decision
          turn 2: end_turn (so Agent stops with stop_reason=end_turn)
        With structured_output_model=CoachDecision:
          turn 0: same info gathering (3 tools)
          turn 1: same action tool
          turn 2: forced structured output (CoachDecision toolUse) — the Agent
                  extracts structured_output and stops.
        """
        # Detect structured-output mode by presence of CoachDecision spec
        has_structured = False
        expected_name: str | None = None
        if tool_specs:
            for s in tool_specs:
                name = s.get("name") if isinstance(s, dict) else getattr(s, "name", None)
                if name == "CoachDecision":
                    expected_name = name
                    has_structured = True
                    break
        # Forced mode: Strands sets tool_choice={"any":{}} and replaces tool_specs with [CoachDecision]
        # That happens on the cycle *after* the previous cycle returned end_turn with structured_output enabled.
        # In that forced cycle we must emit the CoachDecision toolUse and finish.
        if (
            has_structured
            and tool_choice is not None
            and isinstance(tool_choice, dict)
            and "any" in tool_choice
        ):
            # Forced structured output cycle — emit CoachDecision
            decision = self._precomputed
            if decision is None:
                from calllens.coach.decisions import DecisionType

                decision = CoachDecision(
                    decision=DecisionType.NO_ACTION,  # type: ignore[arg-type]
                    confidence=0.89,
                    summary="No material coaching or escalation condition detected.",
                    reason="No material coaching or escalation condition detected — silence is the correct action.",
                    evidence=[],
                    metrics={},
                    human_review_required=False,
                    call_id=self._call_id,
                    rubric_name=self._rubric_name,
                    model_provider="mock",
                )
            import contextlib as _ctx2

            with _ctx2.suppress(Exception):
                if not decision.call_id:
                    decision.call_id = self._call_id
                if not decision.rubric_name:
                    decision.rubric_name = self._rubric_name
                decision.model_provider = "mock"
            payload = decision.model_dump(mode="json")
            async for ev in self._yield_tool_calls([{"name": expected_name, "input": payload}]):  # type: ignore[arg-type]
                yield ev
            return

        # Normal (and first) tool loop — two turns of real tools before the forced cycle.
        turn = self._turn
        self._turn += 1

        decision_type = None
        import contextlib as _ctx3

        decision_type = "NO_ACTION"
        with _ctx3.suppress(Exception):
            decision_type = self._precomputed.decision.value if self._precomputed else "NO_ACTION"  # type: ignore[union-attr]

        call_id = self._call_id or "coach-call"
        evidence_stub: list[dict[str, Any]] = []
        with _ctx3.suppress(Exception):
            if self._precomputed and self._precomputed.evidence:
                evidence_stub = [e.model_dump(mode="json") for e in self._precomputed.evidence[:1]]

        if turn == 0:
            calls: list[dict[str, Any]] = [
                {
                    "name": "check_escalation_signals",
                    "input": {
                        "call_id": call_id,
                        "transcript_snippet": (self._transcript[:300] if self._transcript else ""),
                    },
                },
                {
                    "name": "get_call_evidence",
                    "input": {"call_id": call_id, "rubric": self._rubric_name},
                },
                {
                    "name": "get_rep_history",
                    "input": {
                        "rep_id": (
                            self._history.rep_id
                            if self._history and hasattr(self._history, "rep_id")
                            else "rep_unknown"
                        )
                    },
                },
            ]
            async for ev in self._yield_tool_calls(calls):
                yield ev
            return

        if turn == 1:
            if decision_type == "ESCALATE":
                reason = "Customer churn / risk signal — manager review required"
                with _ctx3.suppress(Exception):
                    if self._precomputed and self._precomputed.reason:
                        reason = self._precomputed.reason
                calls = [
                    {
                        "name": "escalate_to_manager",
                        "input": {
                            "call_id": call_id,
                            "reason": reason,
                            "evidence": evidence_stub,
                            "urgency": "high",
                        },
                    }
                ]
            elif decision_type == "COACH":
                msg = "On your next call, pause after the customer raises a concern and ask one discovery question before proposing a solution."
                with _ctx3.suppress(Exception):
                    if self._precomputed and self._precomputed.recommended_action:
                        msg = self._precomputed.recommended_action.message  # type: ignore[union-attr]
                calls = [
                    {
                        "name": "create_coaching_action",
                        "input": {"call_id": call_id, "message": msg, "evidence": evidence_stub},
                    }
                ]
            else:
                no_action_payload: dict[str, Any] = {"decision": "NO_ACTION", "confidence": 0.89}
                with _ctx3.suppress(Exception):
                    if self._precomputed:
                        no_action_payload = self._precomputed.model_dump(mode="json")
                calls = [
                    {"name": "record_agent_decision", "input": {"decision": no_action_payload}}
                ]
            async for ev in self._yield_tool_calls(calls):
                yield ev
            return

        # turn >=2 without forced structured output (agent called without structured_output_model): finish.
        yield {"messageStart": {"role": "assistant"}}
        yield {"contentBlockStart": {"start": {}}}
        yield {"contentBlockDelta": {"delta": {"text": "Proceeding to structured decision."}}}
        yield {"contentBlockStop": {}}
        yield {"messageStop": {"stopReason": "end_turn"}}
        yield {
            "metadata": {
                "usage": {"inputTokens": 5, "outputTokens": 5, "totalTokens": 10},
                "metrics": {"latencyMs": 0},
            }
        }

    async def _yield_tool_calls(self, calls: list[dict[str, Any]]):  # type: ignore[no-untyped-def]
        """Yield StreamEvent sequence for one assistant turn with N toolUses."""
        yield {"messageStart": {"role": "assistant"}}
        for c in calls:
            tid = f"toolu_{uuid.uuid4().hex[:8]}"
            name = c["name"]
            inp = c["input"]
            # Ensure input is JSON-serializable dict
            if not isinstance(inp, dict):
                inp = {"value": inp}
            inp_str = json.dumps(inp, ensure_ascii=False)
            yield {"contentBlockStart": {"start": {"toolUse": {"name": name, "toolUseId": tid}}}}
            # Strands expects the input JSON as a single delta chunk (can be split, but one is fine)
            yield {"contentBlockDelta": {"delta": {"toolUse": {"input": inp_str}}}}
            yield {"contentBlockStop": {}}
        yield {"messageStop": {"stopReason": "tool_use"}}
        yield {
            "metadata": {
                "usage": {"inputTokens": 10, "outputTokens": 20, "totalTokens": 30},
                "metrics": {"latencyMs": 5},
            }
        }
