"""LLM provider errors."""

from __future__ import annotations


class LLMError(RuntimeError):
    """Base class for LLM provider failures."""


class LLMNotConfigured(LLMError):
    """Raised when the selected provider lacks credentials."""


class LLMOutputError(LLMError):
    """Raised when model output cannot be parsed into the requested schema."""
