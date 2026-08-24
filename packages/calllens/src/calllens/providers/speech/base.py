"""Speech provider abstraction.

CallLens must not be tightly coupled to ElevenLabs. Business logic depends
only on this Protocol; concrete providers (ElevenLabs, mock, future vendors)
implement it.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from calllens.domain.transcript import Transcript


@runtime_checkable
class SpeechProvider(Protocol):
    """Transcribe audio and synthesize speech."""

    async def transcribe(self, audio: bytes, *, language: str | None = None) -> Transcript:
        """Transcribe audio bytes into a diarized, timestamped transcript."""
        ...

    async def transcribe_stream(
        self, audio: bytes, *, language: str | None = None
    ) -> AsyncIterator[Transcript]:
        """Yield incremental transcripts while audio is still being received."""
        ...

    async def synthesize(self, text: str) -> bytes:
        """Synthesize speech audio (e.g. for spoken coaching)."""
        ...
