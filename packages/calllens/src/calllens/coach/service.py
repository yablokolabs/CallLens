"""Coach service — wires FastAPI, storage, analysis, history, and the Strands agent.

Keeps the conversation-intelligence engine (CallLens graph) separate from the
agentic-ai orchestration (Strands). This service owns persistence of
CoachDecision records alongside the existing CallReport storage.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from calllens.coach.decisions import CoachDecision
from calllens.coach.demo import build_demo_calls, build_history_seeds
from calllens.coach.history import InMemoryHistoryStore, get_history_store
from calllens.config import Settings, get_settings
from calllens.domain.report import CallReport


async def _analyze_transcript(transcript: str, rubric_name: str, settings: Settings) -> CallReport:
    """Run the CallLens graph (conversation-intelligence) and return a CallReport."""
    import contextlib

    from calllens.graphs import AnalysisGraph
    from calllens.ingest.parsers import parse_transcript_text
    from calllens.rubrics.loader import load_rubric
    from calllens.testing import build_mock_llm

    parsed = parse_transcript_text(transcript)
    rubric = load_rubric(f"{settings.rubrics_dir}/{rubric_name}.yaml")
    llm = build_mock_llm(parsed)
    graph = AnalysisGraph(llm=llm, settings=settings, rubric=rubric)
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
    # Stash raw text for transcript-level escalation supplement (demo path)
    with contextlib.suppress(Exception):
        object.__setattr__(report, "_raw_transcript_text", transcript)  # type: ignore[attr-defined]
    return report  # type: ignore[return-value]


def _sync_analyze(transcript: str, rubric_name: str, settings: Settings) -> CallReport:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_analyze_transcript(transcript, rubric_name, settings))
    else:
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(
                asyncio.run, _analyze_transcript(transcript, rubric_name, settings)
            ).result()


@dataclass
class CoachService:
    settings: Settings = field(default_factory=get_settings)
    history_store: InMemoryHistoryStore = field(default_factory=get_history_store)
    _decisions: dict[str, CoachDecision] = field(default_factory=dict)
    _reports: dict[str, CallReport] = field(default_factory=dict)
    _seeded: bool = False
    _seeding: bool = False
    _seed_error: str | None = None

    def _agent(self):
        from calllens.coach.agent import CoachAgent

        return CoachAgent(settings=self.settings)

    def ensure_seed(self) -> None:
        if self._seeded:
            return
        for rep_id, records in build_history_seeds().items():
            self.history_store.seed(rep_id, records)
        self._seeded = True

    async def evaluate_transcript(
        self,
        transcript: str,
        *,
        rubric_name: str = "consultative_sales",
        rep_id: str | None = None,
        call_id: str | None = None,
    ) -> CoachDecision:
        import contextlib

        self.ensure_seed()
        report = await _analyze_transcript(transcript, rubric_name, self.settings)
        if call_id:
            report.call_id = call_id  # type: ignore[attr-defined]
        # Attach raw transcript for escalation supplement
        with contextlib.suppress(Exception):
            object.__setattr__(report, "_raw_transcript_text", transcript)  # type: ignore[attr-defined]
        decision = self._decide_from_report(report, rep_id=rep_id, raw_transcript=transcript)
        key = decision.call_id or report.call_id
        self._reports[key] = report
        self._decisions[key] = decision
        return decision

    def evaluate_transcript_sync(
        self,
        transcript: str,
        *,
        rubric_name: str = "consultative_sales",
        rep_id: str | None = None,
        call_id: str | None = None,
    ) -> CoachDecision:
        import contextlib

        self.ensure_seed()
        report = _sync_analyze(transcript, rubric_name, self.settings)
        if call_id:
            report.call_id = call_id  # type: ignore[attr-defined]
        with contextlib.suppress(Exception):
            object.__setattr__(report, "_raw_transcript_text", transcript)  # type: ignore[attr-defined]
        decision = self._decide_from_report(report, rep_id=rep_id, raw_transcript=transcript)
        key = decision.call_id or report.call_id
        self._reports[key] = report
        self._decisions[key] = decision
        return decision

    def _decide_from_report(
        self, report: CallReport, *, rep_id: str | None, raw_transcript: str | None
    ) -> CoachDecision:
        """Strands is the decision layer — CallLens is the evidence layer.

        The Strands Coach Agent owns tool selection, evidence gathering,
        history use, decision choice, and the action tool. Deterministic
        policy is only guardrails/validation/fallback inside the agent.
        """
        import contextlib

        # Stash raw text + report so agent tools (get_call_evidence,
        # check_escalation_signals) can find this call during the loop.
        if raw_transcript:
            with contextlib.suppress(Exception):
                object.__setattr__(report, "_raw_transcript_text", raw_transcript)  # type: ignore[attr-defined]
        import contextlib as _ctx2

        with _ctx2.suppress(Exception):
            self._reports[str(report.call_id)] = report  # type: ignore[attr-defined]

        history = self.history_store.summary(rep_id) if rep_id else None
        agent = self._agent()
        try:
            decision = agent.evaluate_report(
                report,
                history=history,
                rep_id=rep_id,
                raw_transcript=raw_transcript,
                rubric_name="consultative_sales",
            )
        except Exception:
            # Absolute safety fallback — deterministic decide is the
            # repair oracle, not the primary engine. This path only runs
            # if the Strands loop itself crashes.
            from calllens.coach.decisions import DecisionType, decide
            from calllens.coach.transcript_keywords import transcript_has_escalation

            provider = (
                self.settings.coach_model_provider
                or self.settings.model_provider
                or self.settings.llm_provider
                or "mock"
            )
            decision = decide(report, history=history, model_provider=str(provider))
            if decision.decision != DecisionType.ESCALATE and raw_transcript:
                should, reason, conf = transcript_has_escalation(raw_transcript)
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
                    decision.recommended_action = RecommendedAction(
                        type=DecisionType.ESCALATE, message=reason, urgency="high"
                    )
                    if not decision.evidence:
                        decision.evidence = [
                            DecisionEvidence(
                                timestamp="00:01:00",
                                seconds=60.0,
                                quote=raw_transcript[:140],
                                reason=reason,
                            )
                        ]
                    decision.trace = [
                        AgentTraceStep(
                            step="Analyzing conversation",
                            status="done",
                            detail="CallLens analysis completed",
                        ),
                        AgentTraceStep(
                            step="Checking evidence",
                            status="done",
                            detail="Transcript escalation signal detected",
                        ),
                        AgentTraceStep(
                            step="Reviewing rep history",
                            status="done",
                            detail=history.note
                            if history and history.note
                            else "5-call window checked",
                        ),
                        AgentTraceStep(
                            step="Decision", status="done", detail="Manager review required"
                        ),
                        AgentTraceStep(
                            step="Action",
                            status="done",
                            detail="Escalation flagged for human review",
                        ),
                    ]
            if rep_id:
                try:
                    self.history_store.record(rep_id, report, decision.decision.value)
                    decision.history_context = self.history_store.summary(rep_id)
                except Exception:
                    pass
            decision.call_id = report.call_id
        # Persist for GET /api/coach/calls/{id}
        with _ctx2.suppress(Exception):
            key = decision.call_id or report.call_id
            self._decisions[str(key)] = decision  # type: ignore[attr-defined]
            self._reports[str(key)] = report  # type: ignore[attr-defined]
        return decision

    def seed_demo(self) -> list[CoachDecision]:
        self.ensure_seed()
        decisions: list[CoachDecision] = []
        for demo in build_demo_calls():
            import contextlib

            report = _sync_analyze(demo.transcript, "consultative_sales", self.settings)
            report.call_id = demo.id  # type: ignore[attr-defined]
            with contextlib.suppress(Exception):
                object.__setattr__(report, "_raw_transcript_text", demo.transcript)  # type: ignore[attr-defined]
            decision = self._decide_from_report(
                report, rep_id=demo.rep_id, raw_transcript=demo.transcript
            )
            decision.call_id = demo.id
            self._reports[demo.id] = report
            self._decisions[demo.id] = decision
            decisions.append(decision)
        # Extra healthy calls so summary matches README screenshot totals (15 / 2 / 1 = 18)
        extra_rep = "rep_extra"
        for i in range(14):
            import contextlib

            cid = f"demo-extra-{i:02d}"
            dem = build_demo_calls()[0]
            report = _sync_analyze(dem.transcript, "consultative_sales", self.settings)
            report.call_id = cid  # type: ignore[attr-defined]
            with contextlib.suppress(Exception):
                object.__setattr__(report, "_raw_transcript_text", dem.transcript)  # type: ignore[attr-defined]
            decision = self._decide_from_report(
                report, rep_id=extra_rep, raw_transcript=dem.transcript
            )
            decision.call_id = cid
            self._reports[cid] = report
            self._decisions[cid] = decision
        # One extra COACH-flavored call
        dem2 = build_demo_calls()[1]
        report2 = _sync_analyze(dem2.transcript, "consultative_sales", self.settings)
        report2.call_id = "demo-extra-coach-01"  # type: ignore[attr-defined]
        import contextlib as _ctx

        with _ctx.suppress(Exception):
            object.__setattr__(report2, "_raw_transcript_text", dem2.transcript)  # type: ignore[attr-defined]
        self.history_store.seed("rep_daniel_extra", build_history_seeds()["rep_daniel"])
        decision2 = self._decide_from_report(
            report2, rep_id="rep_daniel_extra", raw_transcript=dem2.transcript
        )
        decision2.call_id = "demo-extra-coach-01"
        self._reports[decision2.call_id] = report2
        self._decisions[decision2.call_id] = decision2
        return decisions

    def list_decisions(self) -> list[CoachDecision]:
        self.ensure_seed()
        if not self._decisions:
            # For live models (e.g. Sarvam) don't auto-seed 18 calls inside
            # a request — that blocks the event loop and hangs /health and /docs.
            # The frontend handles empty -> "Load Demo Calls" -> POST /seed.
            try:
                provider = (
                    self.settings.coach_model_provider
                    or self.settings.model_provider
                    or self.settings.llm_provider
                    or "mock"
                ).lower()
                if provider not in ("mock", ""):
                    return []
            except Exception:
                pass
            self.seed_demo()
        return sorted(self._decisions.values(), key=lambda d: d.call_id or "")

    def get_decision(self, call_id: str) -> CoachDecision | None:
        self.ensure_seed()
        # Don't auto-seed a full 18-call batch for a single missing id when live.
        return self._decisions.get(call_id)

    def get_report(self, call_id: str) -> CallReport | None:
        return self._reports.get(call_id)

    def summary(self) -> dict:
        # Never block /summary on a full Sarvam seed — defer until explicit POST /seed.
        # The frontend handles empty -> Load Demo Calls.
        try:
            provider = (
                self.settings.coach_model_provider
                or self.settings.model_provider
                or self.settings.llm_provider
                or "mock"
            ).lower()
            if provider not in ("mock", "") and not self._decisions:
                self.ensure_seed()
                if self._seeding:
                    return {
                        "total": 0,
                        "by_decision": {"NO_ACTION": 0, "COACH": 0, "ESCALATE": 0},
                        "today_label": "TODAY",
                        "demo_seeded": False,
                        "seed_pending": True,
                        "seeding": True,
                    }
                if self._seed_error:
                    return {
                        "total": 0,
                        "by_decision": {"NO_ACTION": 0, "COACH": 0, "ESCALATE": 0},
                        "today_label": "TODAY",
                        "demo_seeded": False,
                        "seed_pending": True,
                        "seed_error": self._seed_error,
                    }
                return {
                    "total": 0,
                    "by_decision": {"NO_ACTION": 0, "COACH": 0, "ESCALATE": 0},
                    "today_label": "TODAY",
                    "demo_seeded": False,
                    "seed_pending": True,
                }
        except Exception:
            pass
        if self._seeding and not self._decisions:
            return {
                "total": 0,
                "by_decision": {"NO_ACTION": 0, "COACH": 0, "ESCALATE": 0},
                "today_label": "TODAY",
                "demo_seeded": False,
                "seed_pending": True,
                "seeding": True,
            }
        decs = self.list_decisions()
        by_decision = {"NO_ACTION": 0, "COACH": 0, "ESCALATE": 0}
        for d in decs:
            by_decision[d.decision.value] += 1
        out: dict = {
            "total": len(decs),
            "by_decision": by_decision,
            "today_label": "TODAY",
            "demo_seeded": self._seeded,
        }
        if self._seeding:
            out["seeding"] = True
        if self._seed_error:
            out["seed_error"] = self._seed_error
        return out

    def rep_history(self, rep_id: str) -> dict:
        # Don't force a full Sarvam seed for a single rep history fetch.
        self.ensure_seed()
        return self.history_store.summary(rep_id).model_dump(mode="json")

    def clear(self) -> None:
        self._decisions.clear()
        self._reports.clear()
        self.history_store.clear()
        self._seeding = False
        self._seed_error = None


_coach_service: CoachService | None = None


def get_coach_service(settings: Settings | None = None) -> CoachService:
    global _coach_service
    if _coach_service is None:
        _coach_service = CoachService(settings=settings or get_settings())
        # Eager DEMO_MODE seeding is only safe for the deterministic mock.
        # With a live model (e.g. Sarvam) seeding 18 calls synchronously inside
        # get_coach_service() blocks the event loop at import time and hangs
        # /health as well, so defer seeding to the first coach request.
        try:
            if _coach_service.settings.demo_mode:
                provider = (
                    _coach_service.settings.coach_model_provider
                    or _coach_service.settings.model_provider
                    or _coach_service.settings.llm_provider
                    or "mock"
                ).lower()
                if provider in ("mock", ""):
                    _coach_service.seed_demo()
        except Exception:
            pass
    return _coach_service
