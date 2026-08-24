"""Deterministic conversation metrics.

These are computed from the transcript with pure arithmetic — no LLM involved.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class TalkRatio(BaseModel):
    """Fraction of total speaking time attributed to each side."""

    representative: float = Field(ge=0, le=1)
    customer: float = Field(ge=0, le=1)
    other: float = Field(default=0, ge=0, le=1)


class SilenceGap(BaseModel):
    """A gap in the conversation with no detected speech."""

    start_time: float
    end_time: float
    duration: float


class CallMetrics(BaseModel):
    """All deterministically computable conversation metrics."""

    duration: float = Field(ge=0)
    total_words: int = Field(ge=0)
    words_per_minute: float = Field(ge=0)
    representative_words: int = Field(ge=0)
    customer_words: int = Field(ge=0)
    representative_speaking_time: float = Field(ge=0)
    customer_speaking_time: float = Field(ge=0)
    talk_ratio: TalkRatio
    turns: int = Field(ge=0)
    speaker_transitions: int = Field(ge=0)
    interruptions: int = Field(ge=0)
    silence_duration: float = Field(ge=0)
    longest_monologue: float = Field(ge=0)
    longest_monologue_speaker: str | None = None
    avg_response_length_words: float = Field(ge=0)
    customer_rep_word_ratio: float = Field(ge=0)
    question_count: int = Field(ge=0)
    open_question_count: int = Field(ge=0)
    silence_gaps: list[SilenceGap] = Field(default_factory=list)
