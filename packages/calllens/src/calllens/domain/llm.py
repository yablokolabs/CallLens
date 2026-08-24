"""Primitives for structured LLM calls."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class LLMCall(BaseModel):
    """A recorded LLM interaction for cost/observability tracking."""

    provider: str
    model: str
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    duration_ms: float = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)
