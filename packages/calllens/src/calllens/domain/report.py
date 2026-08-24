"""Call report and auditability domain models.

Every analysis records the exact model/provider/prompt/rubric/pipeline
versions that produced it so results are auditable and drift-monitorable.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from calllens.domain.coaching import CoachingInsight
from calllens.domain.metrics import CallMetrics
from calllens.domain.opportunities import Opportunity, Risk
from calllens.domain.scoring import RubricScore
from calllens.domain.sentiment import SentimentAnalysis
from calllens.domain.topics import Topic


class AnalysisStatus(StrEnum):
    UPLOADED = "UPLOADED"
    TRANSCRIBING = "TRANSCRIBING"
    TRANSCRIBED = "TRANSCRIBED"
    ANALYZING = "ANALYZING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ModelIdentity(BaseModel):
    """Identifies the exact model versions that produced an analysis."""

    model_provider: str
    model_name: str
    model_version: str | None = None
    prompt_version: str = "1.0"
    rubric_version: str | None = None
    pipeline_version: str = "0.1.0"


class UsageRecord(BaseModel):
    """AI provider usage tracked per analysis."""

    stt_seconds: float = Field(default=0, ge=0)
    stt_requests: int = Field(default=0, ge=0)
    llm_requests: int = Field(default=0, ge=0)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    tts_characters: int = Field(default=0, ge=0)
    estimated_cost_usd: float = Field(default=0, ge=0)


class CallReport(BaseModel):
    """The complete, evidence-backed analysis of one call."""

    call_id: str
    status: AnalysisStatus = AnalysisStatus.COMPLETED
    overall_score: float = Field(ge=0, le=100)
    summary: str = ""
    confidence: float = Field(ge=0, le=1)
    metrics: CallMetrics | None = None
    sentiment: SentimentAnalysis | None = None
    topics: list[Topic] = Field(default_factory=list)
    rubric_scores: list[RubricScore] = Field(default_factory=list)
    opportunities: list[Opportunity] = Field(default_factory=list)
    risks: list[Risk] = Field(default_factory=list)
    coaching: list[CoachingInsight] = Field(default_factory=list)
    model_identity: ModelIdentity | None = None
    usage: UsageRecord = Field(default_factory=UsageRecord)
    analysis_run_id: str | None = None


class AnalysisRun(BaseModel):
    """Metadata describing a single pipeline execution."""

    id: str
    call_id: str
    organization_id: str | None = None
    status: AnalysisStatus = AnalysisStatus.UPLOADED
    rubric_name: str | None = None
    rubric_version: str | None = None
    error: str | None = None
    model_identity: ModelIdentity | None = None
    usage: UsageRecord = Field(default_factory=UsageRecord)
    created_at: str | None = None
