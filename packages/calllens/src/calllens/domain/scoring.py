"""Evidence-backed scoring domain models.

Every semantic score references timestamped evidence extracted from the
conversation so users can click a timestamp and jump to the audio.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Evidence(BaseModel):
    """A timestamped excerpt supporting or contradicting a score."""

    start_time: float = Field(ge=0)
    end_time: float | None = Field(default=None, ge=0)
    speaker_id: str
    transcript_excerpt: str
    explanation: str
    kind: str = "positive"  # "positive" | "negative"


class RubricResult(BaseModel):
    """Score for a single rubric dimension with full evidence."""

    rubric_dimension: str
    score: float = Field(ge=0, le=10)
    confidence: float = Field(ge=0, le=1)
    reasoning: str
    positive_evidence: list[Evidence] = Field(default_factory=list)
    negative_evidence: list[Evidence] = Field(default_factory=list)
    missing_behaviors: list[str] = Field(default_factory=list)
    rescore_attempts: int = Field(default=0, ge=0)


class RubricScore(BaseModel):
    """A named dimension's result inside a scored rubric."""

    dimension: str
    label: str
    weight: float = Field(ge=0, le=1)
    result: RubricResult
