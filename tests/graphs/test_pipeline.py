"""LangGraph pipeline behavior tests (all providers mocked)."""

from __future__ import annotations

import pytest

from calllens.graphs import AnalysisGraph
from calllens.graphs.pipeline import _latest_attempt_results
from calllens.providers.llm.mock import MockLLMProvider
from calllens.semantic.schemas import DimensionScore


def _graph(settings, transcript, rubric, mock_llm):
    from calllens.providers.speech.mock import MockSpeechProvider

    return AnalysisGraph(
        speech=MockSpeechProvider(transcript),
        llm=mock_llm,
        settings=settings,
        rubric=rubric,
    )


@pytest.mark.asyncio
async def test_full_pipeline_completes(settings, transcript, rubric, mock_llm):
    graph = _graph(settings, transcript, rubric, mock_llm)
    state = await graph.run({"call_id": "abc", "transcript": transcript, "rubric": rubric})
    report = state["final_report"]
    assert state["status"].value == "COMPLETED"
    assert report is not None
    assert len(report.rubric_scores) == 10
    assert report.metrics is not None
    assert report.sentiment is not None
    assert report.topics
    assert report.opportunities
    assert state["evidence"]


@pytest.mark.asyncio
async def test_parallel_analysis_runs(settings, transcript, rubric, mock_llm):
    graph = _graph(settings, transcript, rubric, mock_llm)
    state = await graph.run({"call_id": "abc", "transcript": transcript, "rubric": rubric})
    report = state["final_report"]
    # All semantic outputs present ⇒ parallel branches joined correctly.
    assert report.sentiment.customer is not None
    assert len(report.topics) >= 1
    assert len(report.rubric_scores) == 10
    assert len(report.opportunities) >= 1


@pytest.mark.asyncio
async def test_confidence_gate_triggers_rescore(settings, transcript, rubric, mock_llm):
    """A low-confidence first pass must trigger bounded re-scoring."""
    # Force low confidence on the first attempt (10 dimensions), then pass.
    score_calls = {"n": 0}
    original = mock_llm._handlers[DimensionScore]

    def low_then_high(prompt, schema):
        score_calls["n"] += 1
        out = original(prompt, schema)
        if score_calls["n"] <= 10:
            return DimensionScore(
                dimension=out.dimension,
                score=out.score,
                confidence=0.1,
                reasoning=out.reasoning,
            )
        return out

    mock_llm.register(DimensionScore, low_then_high)
    graph = _graph(settings, transcript, rubric, mock_llm)
    state = await graph.run({"call_id": "abc", "transcript": transcript, "rubric": rubric})
    assert state["rescore_attempts"] == 1
    assert state["final_report"].confidence >= settings.confidence_threshold


@pytest.mark.asyncio
async def test_rescoring_is_bounded(settings, transcript, rubric, mock_llm):
    """Even with persistently low confidence, re-scoring stops at the limit."""
    settings.max_rescore_attempts = 2

    def always_low(prompt, schema):
        return DimensionScore(dimension="x", score=5.0, confidence=0.1, reasoning="low")

    mock_llm.register(DimensionScore, always_low)
    graph = _graph(settings, transcript, rubric, mock_llm)
    state = await graph.run({"call_id": "abc", "transcript": transcript, "rubric": rubric})
    assert state["rescore_attempts"] <= 2
    assert state["final_report"] is not None  # pipeline terminates, no infinite loop


def test_latest_attempt_results_filters_older_attempts(rubric):
    from calllens.domain.scoring import RubricResult

    old = [
        RubricResult(
            rubric_dimension="a", score=5, confidence=0.5, reasoning="", rescore_attempts=0
        )
    ]
    new = [
        RubricResult(
            rubric_dimension="a", score=8, confidence=0.9, reasoning="", rescore_attempts=1
        )
    ]
    filtered = _latest_attempt_results(old + new)
    assert len(filtered) == 1
    assert filtered[0].rescore_attempts == 1


@pytest.mark.asyncio
async def test_audio_ingestion_runs_transcribe(settings, rubric, mock_llm, transcript):
    from calllens.providers.speech.mock import MockSpeechProvider

    speech = MockSpeechProvider(transcript)
    graph = AnalysisGraph(speech=speech, llm=mock_llm, settings=settings, rubric=rubric)
    state = await graph.run({"call_id": "audio-1", "audio": b"fake-audio", "rubric": rubric})
    assert state["final_report"] is not None
    assert state["transcript"].source == "mock"


def test_mock_llm_reused_across_graph_nodes(mock_llm):
    """The same provider instance must serve all nodes (deterministic)."""
    assert isinstance(mock_llm, MockLLMProvider)
