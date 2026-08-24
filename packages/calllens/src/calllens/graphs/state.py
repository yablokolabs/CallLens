"""Strongly typed LangGraph state for the analysis pipeline."""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from calllens.domain.coaching import CoachingInsight
from calllens.domain.metrics import CallMetrics
from calllens.domain.opportunities import Opportunity, Risk
from calllens.domain.report import AnalysisStatus, CallReport, ModelIdentity, UsageRecord
from calllens.domain.rubric import Rubric, RubricDimension
from calllens.domain.scoring import Evidence, RubricResult, RubricScore
from calllens.domain.sentiment import SentimentAnalysis
from calllens.domain.topics import Intent, Topic
from calllens.domain.transcript import Speaker, Transcript


class ConversationState(TypedDict, total=False):
    """State flowing through the CallLens analysis graph."""

    call_id: str
    organization_id: str | None
    analysis_run_id: str | None
    audio_uri: str | None
    audio: bytes | None
    transcript: Transcript | None
    language: str | None
    speakers: list[Speaker]
    rubric: Rubric | None
    rubric_name: str | None

    # Fan-out payload channels (used by Send tasks only, never written back).
    dim: RubricDimension | None
    attempt: int

    deterministic_metrics: CallMetrics | None
    sentiment: SentimentAnalysis | None
    topics: list[Topic] | None
    intents: list[Intent] | None

    rubric_results: Annotated[list[RubricResult], operator.add]
    rubric_scores: list[RubricScore] | None
    opportunities: list[Opportunity] | None
    risks: list[Risk] | None
    evidence: list[Evidence] | None
    coaching: list[CoachingInsight] | None

    confidence: float | None
    validation_errors: Annotated[list[str], operator.add]
    rescore_attempts: int

    status: AnalysisStatus
    model_identity: ModelIdentity | None
    usage: UsageRecord

    final_report: CallReport | None
