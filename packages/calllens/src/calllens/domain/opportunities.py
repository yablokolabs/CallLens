"""Opportunity and risk domain models."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class OpportunityType(StrEnum):
    UPSELL = "upsell"
    CROSS_SELL = "cross_sell"
    BUDGET_SIGNAL = "budget_signal"
    BUYING_INTENT = "buying_intent"
    PURCHASE_TIMELINE = "purchase_timeline"
    DECISION_MAKER = "decision_maker"


class Opportunity(BaseModel):
    """A detected commercial opportunity with supporting evidence."""

    type: OpportunityType
    confidence: float = Field(ge=0, le=1)
    description: str
    product_context: str | None = None
    evidence_timestamps: list[float] = Field(default_factory=list)


class RiskType(StrEnum):
    OBJECTION = "objection"
    UNRESOLVED_CONCERN = "unresolved_concern"
    COMPETITOR = "competitor"
    MISSED_FOLLOW_UP = "missed_follow_up"
    OTHER = "other"


class Risk(BaseModel):
    """A detected risk with supporting evidence."""

    type: RiskType
    confidence: float = Field(ge=0, le=1)
    description: str
    evidence_timestamps: list[float] = Field(default_factory=list)
