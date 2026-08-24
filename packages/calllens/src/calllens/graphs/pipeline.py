"""The CallLens analysis graph.

Pipeline: ingest → transcribe → normalize → parallel [metrics | semantic
(sentiment ‖ topics ‖ intents)] → parallel [rubric scoring (per-dimension
fan-out) | opportunities] → evidence aggregation → consistency → confidence
gate → (bounded re-score) → coaching → report.

Independent work runs in parallel; the confidence gate prevents blind trust
in first-pass LLM results and re-evaluation is bounded by
``max_rescore_attempts``. Per-dimension scoring uses LangGraph ``Send``
fan-out so all dimensions are scored concurrently.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, Send

from calllens.config import Settings, get_settings
from calllens.domain.report import AnalysisStatus, CallReport, ModelIdentity, UsageRecord
from calllens.domain.rubric import Rubric, RubricDimension
from calllens.domain.scoring import RubricResult, RubricScore
from calllens.domain.transcript import SpeakerRole, Transcript
from calllens.graphs.state import ConversationState
from calllens.metrics import compute_call_metrics
from calllens.providers.llm.base import LLMProvider
from calllens.providers.speech.base import SpeechProvider
from calllens.rubrics.engine import RubricEngine
from calllens.scoring.pipeline import RubricScoringPipeline
from calllens.semantic import (
    CoachingGenerator,
    OpportunityDetector,
    SentimentAnalyzer,
    TopicExtractor,
)

logger = logging.getLogger(__name__)

PIPELINE_VERSION = "0.1.0"


class AnalysisGraph:
    """Builds and runs the LangGraph analysis pipeline."""

    def __init__(
        self,
        speech: SpeechProvider | None = None,
        llm: LLMProvider | None = None,
        settings: Settings | None = None,
        rubric: Rubric | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        from calllens.providers.llm import get_llm_provider
        from calllens.providers.speech import get_speech_provider

        self.speech = speech or get_speech_provider(
            self.settings, force_mock=not self.settings.speech_enabled
        )
        self.llm = llm or get_llm_provider(self.settings, force_mock=True)
        self.rubric = rubric
        self.graph = self._build()

    # ── Node implementations ──────────────────────────────────────────

    async def _ingest(self, state: ConversationState) -> dict[str, Any]:
        transcript = state.get("transcript")
        if transcript is None and state.get("audio") is not None:
            return {"status": AnalysisStatus.TRANSCRIBING}
        return {
            "status": AnalysisStatus.TRANSCRIBED if transcript else AnalysisStatus.UPLOADED,
            "transcript": transcript,
        }

    async def _transcribe(self, state: ConversationState) -> dict[str, Any]:
        audio = state.get("audio")
        if audio is None:
            return {"status": AnalysisStatus.TRANSCRIBED}
        transcript = await self.speech.transcribe(audio, language=state.get("language"))
        return {"transcript": transcript, "status": AnalysisStatus.TRANSCRIBED}

    async def _normalize(self, state: ConversationState) -> dict[str, Any]:
        transcript = state.get("transcript")
        if transcript is None:
            return {}
        roles = transcript.speaker_roles()
        if not any(r != SpeakerRole.UNKNOWN for r in roles.values()):
            for idx, speaker in enumerate(transcript.speakers):
                if idx == 0:
                    speaker.role = SpeakerRole.REPRESENTATIVE
                elif idx == 1:
                    speaker.role = SpeakerRole.CUSTOMER
        if transcript.duration is None and transcript.utterances:
            ends = [u.end_time for u in transcript.utterances if u.end_time is not None]
            if ends:
                transcript.duration = max(ends)
        return {"transcript": transcript, "speakers": transcript.speakers}

    async def _metrics(self, state: ConversationState) -> dict[str, Any]:
        transcript = state.get("transcript")
        if transcript is None:
            return {}
        return {"deterministic_metrics": compute_call_metrics(transcript)}

    async def _sentiment(self, state: ConversationState) -> dict[str, Any]:
        transcript = state.get("transcript")
        if transcript is None:
            return {}
        sentiment = await SentimentAnalyzer(self.llm).analyze(transcript)
        return {"sentiment": sentiment}

    async def _topics(self, state: ConversationState) -> dict[str, Any]:
        transcript = state.get("transcript")
        if transcript is None:
            return {}
        topics = await TopicExtractor(self.llm).extract(transcript)
        return {"topics": topics}

    async def _intents(self, state: ConversationState) -> dict[str, Any]:
        transcript = state.get("transcript")
        if transcript is None:
            return {}
        intents = await TopicExtractor(self.llm).extract(transcript)
        return {"intents": intents}

    async def _opportunities(self, state: ConversationState) -> dict[str, Any]:
        transcript = state.get("transcript")
        if transcript is None:
            return {}
        opportunities, risks = await OpportunityDetector(self.llm).detect(transcript)
        return {"opportunities": opportunities, "risks": risks}

    async def _rubric_scoring(self, state: ConversationState) -> dict[str, Any] | Command:
        rubric = state.get("rubric")
        transcript = state.get("transcript")
        if rubric is None or transcript is None:
            return {}
        attempt = state.get("rescore_attempts", 0)
        sends = [
            Send("score_dimension", {"dim": dim, "transcript": transcript, "attempt": attempt})
            for dim in rubric.dimensions
        ]
        return Command(goto=sends)

    async def _score_dimension(self, payload: dict[str, Any]) -> dict[str, Any]:
        dim: RubricDimension = payload["dim"]
        transcript: Transcript = payload["transcript"]
        attempt: int = payload["attempt"]
        pipeline = RubricScoringPipeline(self.llm, self.settings)
        result = await pipeline._score_dimension(dim, transcript)  # noqa: SLF001 - intentional reuse
        result.rescore_attempts = attempt
        return {"rubric_results": [result]}

    async def _aggregate_evidence(self, state: ConversationState) -> dict[str, Any]:
        results = _latest_attempt_results(state.get("rubric_results") or [])
        evidence = [e for r in results for e in r.positive_evidence + r.negative_evidence]
        rubric = state.get("rubric")
        scores: list[RubricScore] = []
        if rubric is not None:
            scores = RubricEngine(rubric).build_scores(results)
        return {"evidence": evidence, "rubric_scores": scores}

    async def _consistency_check(self, state: ConversationState) -> dict[str, Any]:
        results = _latest_attempt_results(state.get("rubric_results") or [])
        rubric = state.get("rubric")
        if not results or rubric is None:
            return {"confidence": 0.0}
        confidence = RubricEngine(rubric).weighted_confidence(results)
        return {"confidence": confidence}

    async def _rescore(self, state: ConversationState) -> dict[str, Any]:
        """Re-score with a bounded internal loop until confidence suffices.

        Runs the per-dimension scoring pipeline inline (no graph re-entry) so
        the number of evaluation attempts is strictly bounded by
        ``max_rescore_attempts``.
        """
        rubric = state.get("rubric")
        transcript = state.get("transcript")
        if rubric is None or transcript is None:
            return {}
        pipeline = RubricScoringPipeline(self.llm, self.settings)
        engine = RubricEngine(rubric)
        results = await pipeline.score_rubric(rubric, transcript)
        attempts = 1
        while (
            engine.weighted_confidence(results) < self.settings.confidence_threshold
            and attempts < self.settings.max_rescore_attempts
        ):
            results = await pipeline.score_rubric(rubric, transcript)
            attempts += 1
        for result in results:
            result.rescore_attempts = attempts
        return {"rubric_results": results, "rescore_attempts": attempts}

    async def _coaching(self, state: ConversationState) -> dict[str, Any]:
        transcript = state.get("transcript")
        if transcript is None:
            return {}
        _, scores = _latest_rubric(state)
        coaching = await CoachingGenerator(self.llm).generate(transcript, scores)
        return {"coaching": coaching}

    async def _report(self, state: ConversationState) -> dict[str, Any]:
        results, scores = _latest_rubric(state)
        rubric = state.get("rubric")
        engine = RubricEngine(rubric) if rubric else None
        overall = engine.overall_score(results) if engine else 0.0
        confidence = (
            engine.weighted_confidence(results) if engine else (state.get("confidence") or 0.0)
        )
        report = CallReport(
            call_id=state["call_id"],
            overall_score=overall,
            summary=_build_summary(state),
            confidence=confidence,
            metrics=state.get("deterministic_metrics"),
            sentiment=state.get("sentiment"),
            topics=state.get("topics") or [],
            rubric_scores=scores,
            opportunities=state.get("opportunities") or [],
            risks=state.get("risks") or [],
            coaching=state.get("coaching") or [],
            model_identity=state.get("model_identity"),
            analysis_run_id=state.get("analysis_run_id"),
        )
        return {"final_report": report, "status": AnalysisStatus.COMPLETED}

    # ── Graph assembly ────────────────────────────────────────────────

    def _confidence_route(self, state: ConversationState) -> str:
        confidence = state.get("confidence") or 0.0
        attempts = state.get("rescore_attempts", 0)
        if (
            confidence < self.settings.confidence_threshold
            and attempts < self.settings.max_rescore_attempts
        ):
            return "rescore"
        return "coaching"

    def _build(self):
        builder: StateGraph[ConversationState] = StateGraph(ConversationState)

        builder.add_node("ingest", self._ingest)  # type: ignore[arg-type]
        builder.add_node("transcribe", self._transcribe)  # type: ignore[arg-type]
        builder.add_node("normalize", self._normalize)  # type: ignore[arg-type]
        builder.add_node("metrics", self._metrics)  # type: ignore[arg-type]
        builder.add_node("sentiment", self._sentiment)  # type: ignore[arg-type]
        builder.add_node("topics", self._topics)  # type: ignore[arg-type]
        builder.add_node("intents", self._intents)  # type: ignore[arg-type]
        builder.add_node("rubric_scoring", self._rubric_scoring)  # type: ignore[arg-type]
        builder.add_node("score_dimension", self._score_dimension)  # type: ignore[arg-type]
        builder.add_node("opportunities", self._opportunities)  # type: ignore[arg-type]
        builder.add_node("aggregate_evidence", self._aggregate_evidence)  # type: ignore[arg-type]
        builder.add_node("consistency", self._consistency_check)  # type: ignore[arg-type]
        builder.add_node("rescore", self._rescore)  # type: ignore[arg-type]
        builder.add_node("coaching", self._coaching)  # type: ignore[arg-type]
        builder.add_node("report", self._report)  # type: ignore[arg-type]

        builder.add_edge(START, "ingest")
        builder.add_conditional_edges(
            "ingest",
            lambda s: "transcribe" if s.get("audio") is not None else "normalize",
            {"transcribe": "transcribe", "normalize": "normalize"},
        )
        builder.add_edge("transcribe", "normalize")
        builder.add_edge("normalize", "metrics")
        builder.add_edge("normalize", "sentiment")
        builder.add_edge("normalize", "topics")
        builder.add_edge("normalize", "intents")
        builder.add_edge("normalize", "rubric_scoring")
        builder.add_edge("normalize", "opportunities")

        builder.add_edge("metrics", "aggregate_evidence")
        builder.add_edge("sentiment", "aggregate_evidence")
        builder.add_edge("topics", "aggregate_evidence")
        builder.add_edge("intents", "aggregate_evidence")
        builder.add_edge("opportunities", "aggregate_evidence")
        builder.add_edge("score_dimension", "aggregate_evidence")

        builder.add_edge("aggregate_evidence", "consistency")
        builder.add_conditional_edges(
            "consistency",
            self._confidence_route,
            {"rescore": "rescore", "coaching": "coaching"},
        )
        builder.add_edge("rescore", "coaching")
        builder.add_edge("coaching", "report")
        builder.add_edge("report", END)

        kwargs: dict[str, Any] = {}
        if self.settings.langgraph_checkpoint:
            try:
                from langgraph.checkpoint.memory import InMemorySaver

                kwargs["checkpointer"] = InMemorySaver()
            except ImportError:  # pragma: no cover
                pass
        return builder.compile(**kwargs)

    # ── Public API ────────────────────────────────────────────────────

    async def run(self, state: ConversationState) -> dict[str, Any]:
        """Execute the pipeline and return the final state."""
        self._ensure_mock_handlers(state.get("transcript"))
        rubric = state.get("rubric")
        initial = dict(state)
        initial.setdefault("call_id", str(uuid.uuid4()))
        initial.setdefault("rubric_results", [])
        initial.setdefault("validation_errors", [])
        initial.setdefault("rescore_attempts", 0)
        initial.setdefault("usage", UsageRecord())
        initial.setdefault("status", AnalysisStatus.UPLOADED)
        rubric_version: str | None = None
        if rubric is not None:
            rubric_version = rubric.version
        initial.setdefault(
            "model_identity",
            ModelIdentity(
                model_provider=self.settings.llm_provider,
                model_name=self.settings.llm_model,
                rubric_version=rubric_version,
                pipeline_version=PIPELINE_VERSION,
            ),
        )
        call_id = initial["call_id"]
        config = {"configurable": {"thread_id": call_id}}
        result = await self.graph.ainvoke(initial, config=config)
        return result

    def _ensure_mock_handlers(self, transcript: Transcript | None) -> None:
        """Bind deterministic handlers to a bare mock LLM (offline dev).

        The provider factory returns an unconfigured MockLLMProvider; without
        handlers it would emit empty structured outputs. This wires the
        transcript-aware handlers used by tests and offline demos.
        """
        from calllens.providers.llm.mock import MockLLMProvider

        if not isinstance(self.llm, MockLLMProvider) or self.llm._handlers:  # noqa: SLF001
            return
        if transcript is None:
            from calllens.providers.speech.mock import sample_transcript

            transcript = sample_transcript()
        from calllens.testing import default_mock_handlers

        for schema, handler in default_mock_handlers(transcript).items():
            self.llm.register(schema, handler)


def _latest_attempt_results(results: list[RubricResult]) -> list[RubricResult]:
    """Keep only results from the most recent scoring attempt."""
    if not results:
        return results
    max_attempt = max(r.rescore_attempts for r in results)
    return [r for r in results if r.rescore_attempts == max_attempt]


def _latest_rubric(state: ConversationState) -> tuple[list[RubricResult], list[RubricScore]]:
    """Latest attempt results plus their rubric metadata (label/weight)."""
    results = _latest_attempt_results(state.get("rubric_results") or [])
    rubric = state.get("rubric")
    scores: list[RubricScore] = []
    if rubric is not None:
        scores = RubricEngine(rubric).build_scores(results)
    return results, scores


def _build_summary(state: ConversationState) -> str:
    transcript = state.get("transcript")
    if transcript is None:
        return ""
    metrics = state.get("deterministic_metrics")
    wpm = metrics.words_per_minute if metrics else 0
    return (
        f"{len(transcript.utterances)} spoken turns, ~{wpm:.0f} words/min, "
        f"{len(state.get('topics') or [])} topics, "
        f"{len(state.get('opportunities') or [])} opportunities, "
        f"{len(state.get('risks') or [])} risks detected."
    )
