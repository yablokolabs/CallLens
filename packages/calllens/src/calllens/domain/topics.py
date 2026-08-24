"""Topic and intent domain models."""

from __future__ import annotations

from pydantic import BaseModel, Field

from calllens.domain.sentiment import SentimentLabel


class Topic(BaseModel):
    """A conversation topic with a time window and sentiment."""

    topic: str
    start_time: float = Field(ge=0)
    end_time: float = Field(ge=0)
    sentiment: SentimentLabel | None = None
    confidence: float = Field(ge=0, le=1)


class Intent(BaseModel):
    """A detected conversational intent (e.g. objection, buying signal)."""

    type: str
    description: str
    confidence: float = Field(ge=0, le=1)
    evidence_timestamps: list[float] = Field(default_factory=list)
