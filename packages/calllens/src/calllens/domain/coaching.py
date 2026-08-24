"""Coaching domain models.

Coaching recommendations must reference actual conversation evidence —
never generic advice.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class CoachingPriority(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CoachingInsight(BaseModel):
    """An evidence-backed coaching recommendation."""

    title: str
    priority: CoachingPriority = CoachingPriority.MEDIUM
    recommendation: str
    rationale: str
    evidence_timestamps: list[float] = Field(default_factory=list)
    suggested_phrasing: str | None = None
