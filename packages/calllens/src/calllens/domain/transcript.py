"""Transcript domain models.

A transcript is a time-ordered list of utterances attributed to speakers.
All timestamps are seconds (float) relative to the start of the recording.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class SpeakerRole(StrEnum):
    """Canonical speaker roles used by analysis and rubric scoring."""

    REPRESENTATIVE = "representative"
    CUSTOMER = "customer"
    UNKNOWN = "unknown"


class Speaker(BaseModel):
    """A distinct speaker in a conversation."""

    id: str
    label: str | None = None
    role: SpeakerRole = SpeakerRole.UNKNOWN
    channel_index: int | None = None


class Utterance(BaseModel):
    """A single spoken turn with timestamps."""

    speaker_id: str
    text: str
    start_time: float = Field(ge=0)
    end_time: float | None = Field(default=None, ge=0)

    @field_validator("end_time")
    @classmethod
    def _end_after_start(cls, v: float | None, info) -> float | None:
        if (
            v is not None
            and info.data.get("start_time") is not None
            and v < info.data["start_time"]
        ):
            raise ValueError("end_time must be >= start_time")
        return v


class Transcript(BaseModel):
    """A normalized, diarized conversation transcript."""

    utterances: list[Utterance]
    speakers: list[Speaker] = Field(default_factory=list)
    language: str | None = None
    source: str = "unknown"  # e.g. "elevenlabs", "json", "text"
    duration: float | None = Field(default=None, ge=0)

    def speaker_roles(self) -> dict[str, SpeakerRole]:
        return {s.id: s.role for s in self.speakers}

    def by_speaker(self, speaker_id: str) -> list[Utterance]:
        return [u for u in self.utterances if u.speaker_id == speaker_id]
