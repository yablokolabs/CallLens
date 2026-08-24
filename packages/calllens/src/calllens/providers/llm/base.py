"""Reasoning LLM provider abstraction.

ElevenLabs is the speech layer; a separate provider abstraction powers all
semantic reasoning (sentiment, rubric scoring, evidence, coaching...).
CallLens never hardcodes the intelligence pipeline to one vendor.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel


@runtime_checkable
class LLMProvider(Protocol):
    """Perform completions and structured completions."""

    async def completion(self, prompt: str, *, system: str | None = None) -> str:
        """Return raw text completion."""
        ...

    async def structured_completion(
        self,
        prompt: str,
        schema: type[BaseModel],
        *,
        system: str | None = None,
    ) -> BaseModel:
        """Return a validated instance of ``schema`` parsed from model output.

        Must raise LLMOutputError when the output cannot be validated so
        callers can retry or degrade deterministically.
        """
        ...
