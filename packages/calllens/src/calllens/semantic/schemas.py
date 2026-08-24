"""Structured output schemas for semantic LLM tasks.

These are the strongly typed contracts every semantic analyzer parses into —
never loose dicts or regex-parsed prose. Every field carries a default so the
offline mock provider can always construct a complete, attribute-safe
instance.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from calllens.domain.sentiment import SentimentLabel
from calllens.domain.topics import Topic


class SentimentSegmentOut(BaseModel):
    speaker_id: str = ""
    start: float = Field(default=0.0, ge=0)
    end: float = Field(default=0.0, ge=0)
    sentiment: SentimentLabel = SentimentLabel.NEUTRAL
    score: float = Field(default=0.0, ge=-1, le=1)
    confidence: float = Field(default=0.0, ge=0, le=1)


class SpeakerSentimentOut(BaseModel):
    speaker_id: str = ""
    timeline: list[SentimentSegmentOut] = Field(default_factory=list)
    overall: SentimentLabel = SentimentLabel.NEUTRAL
    average_score: float = Field(default=0.0, ge=-1, le=1)


class TurningPointOut(BaseModel):
    timestamp: float = Field(default=0.0, ge=0)
    from_sentiment: SentimentLabel = SentimentLabel.NEUTRAL
    to_sentiment: SentimentLabel = SentimentLabel.NEUTRAL
    trigger: str | None = None


class SentimentOutput(BaseModel):
    customer: SpeakerSentimentOut | None = None
    representative: SpeakerSentimentOut | None = None
    turning_points: list[TurningPointOut] = Field(default_factory=list)
    engagement: float = Field(default=0.5, ge=0, le=1)
    frustration: float = Field(default=0.0, ge=0, le=1)
    enthusiasm: float = Field(default=0.0, ge=0, le=1)
    uncertainty: float = Field(default=0.0, ge=0, le=1)
    objection_intensity: float = Field(default=0.0, ge=0, le=1)


class TopicOutput(BaseModel):
    topics: list[Topic] = Field(default_factory=list)


class IntentOut(BaseModel):
    type: str = ""
    description: str = ""
    confidence: float = Field(default=0.0, ge=0, le=1)
    evidence_timestamps: list[float] = Field(default_factory=list)


class IntentOutput(BaseModel):
    intents: list[IntentOut] = Field(default_factory=list)


class EvidenceCandidate(BaseModel):
    start_time: float = Field(default=0.0, ge=0)
    speaker: Literal["representative", "customer"] = "representative"
    transcript_excerpt: str = ""
    explanation: str = ""


class EvidenceCandidates(BaseModel):
    dimension: str = ""
    positive: list[EvidenceCandidate] = Field(default_factory=list)
    negative: list[EvidenceCandidate] = Field(default_factory=list)
    missing_behaviors: list[str] = Field(default_factory=list)


class DimensionScore(BaseModel):
    dimension: str = ""
    score: float = Field(default=5.0, ge=0, le=10)
    confidence: float = Field(default=0.5, ge=0, le=1)
    reasoning: str = ""


class OpportunityOut(BaseModel):
    type: str = ""
    confidence: float = Field(default=0.0, ge=0, le=1)
    description: str = ""
    product_context: str | None = None
    evidence_timestamps: list[float] = Field(default_factory=list)


class RiskOut(BaseModel):
    type: str = ""
    confidence: float = Field(default=0.0, ge=0, le=1)
    description: str = ""
    evidence_timestamps: list[float] = Field(default_factory=list)


class OpportunitiesOutput(BaseModel):
    opportunities: list[OpportunityOut] = Field(default_factory=list)
    risks: list[RiskOut] = Field(default_factory=list)


class CoachingOut(BaseModel):
    title: str = ""
    priority: Literal["high", "medium", "low"] = "medium"
    recommendation: str = ""
    rationale: str = ""
    evidence_timestamps: list[float] = Field(default_factory=list)
    suggested_phrasing: str | None = None


class CoachingOutput(BaseModel):
    recommendations: list[CoachingOut] = Field(default_factory=list)
