"""Sentiment analysis domain models.

Sentiment is represented longitudinally (segments over time) and separately
per speaker. Inferred sentiments carry a confidence score.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class SentimentLabel(StrEnum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    CONCERNED = "concerned"
    FRUSTRATED = "frustrated"
    ENTHUSIASTIC = "enthusiastic"
    UNCERTAIN = "uncertain"


class SentimentSegment(BaseModel):
    """Sentiment over a time window for one speaker."""

    speaker_id: str
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    sentiment: SentimentLabel
    score: float = Field(ge=-1, le=1)
    confidence: float = Field(ge=0, le=1)


class TurningPoint(BaseModel):
    """A moment where sentiment direction changed materially."""

    timestamp: float = Field(ge=0)
    from_sentiment: SentimentLabel
    to_sentiment: SentimentLabel
    trigger: str | None = None


class SpeakerSentiment(BaseModel):
    """Longitudinal sentiment timeline for a single speaker."""

    speaker_id: str
    timeline: list[SentimentSegment]
    overall: SentimentLabel
    average_score: float = Field(ge=-1, le=1)


class SentimentAnalysis(BaseModel):
    """Complete sentiment picture for a call."""

    customer: SpeakerSentiment | None = None
    representative: SpeakerSentiment | None = None
    turning_points: list[TurningPoint] = Field(default_factory=list)
    engagement: float = Field(ge=0, le=1)
    frustration: float = Field(ge=0, le=1)
    enthusiasm: float = Field(ge=0, le=1)
    uncertainty: float = Field(ge=0, le=1)
    objection_intensity: float = Field(ge=0, le=1)
