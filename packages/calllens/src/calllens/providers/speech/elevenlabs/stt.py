"""ElevenLabs Speech-to-Text integration (Scribe v2).

Converts a raw audio payload into a diarized, timestamped Transcript using the
current SDK surface: ``client.speech_to_text.convert(...)`` with word-level
timestamps and speaker diarization.

See docs/ELEVENLABS.md for the API contract this provider targets.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from calllens.config import Settings, get_settings
from calllens.domain.transcript import Speaker, Transcript, Utterance
from calllens.providers.speech.elevenlabs.client import (
    ElevenLabsError,
    get_elevenlabs_client,
)

logger = logging.getLogger(__name__)

# Word types emitted by Scribe that represent spoken content we keep.
_KEEP_WORD_TYPES = {"word", "punctuation"}

# Punctuation tokens join directly to the previous word (no space).
_PUNCT_JOIN_RE = re.compile(r"\s+([.,!?;:’')\]}])")


def _join_words(words: list[str]) -> str:
    """Join word tokens, attaching punctuation to the previous word."""
    joined = " ".join(words).strip()
    return _PUNCT_JOIN_RE.sub(r"\1", joined)


@dataclass
class STTResult:
    """Normalized result of one STT call."""

    language: str | None = None
    language_probability: float = 0.0
    audio_duration_secs: float | None = None
    words: list[dict] = field(default_factory=list)


def _words_to_transcript(result: STTResult, source: str = "elevenlabs") -> Transcript:
    """Group word-level tokens into speaker-attributed utterances."""
    utterances: list[Utterance] = []
    current_speaker: str | None = None
    current_words: list[dict] = []
    start_time: float | None = None

    def flush() -> None:
        nonlocal current_words, current_speaker, start_time
        if not current_words or current_speaker is None:
            current_words, current_speaker, start_time = [], None, None
            return
        text = _join_words([w["text"] for w in current_words])
        if text:
            utterances.append(
                Utterance(
                    speaker_id=current_speaker,
                    text=text,
                    start_time=float(start_time or 0.0),
                    end_time=float(current_words[-1]["end"]),
                )
            )
        current_words, current_speaker, start_time = [], None, None

    for word in result.words:
        wtype = str(word.get("type") or "word")
        if wtype not in _KEEP_WORD_TYPES:
            continue
        speaker = str(word.get("speaker_id") or "unknown")
        if speaker != current_speaker:
            flush()
            current_speaker = speaker
            start_time = float(word.get("start") or 0.0)
        current_words.append(
            {
                "text": str(word.get("text", "")),
                "start": float(word.get("start") or 0.0),
                "end": float(word.get("end") or 0.0),
            }
        )
    flush()

    speaker_ids = sorted({u.speaker_id for u in utterances})
    speakers = [Speaker(id=sid) for sid in speaker_ids]
    duration = result.audio_duration_secs
    return Transcript(
        utterances=utterances,
        speakers=speakers,
        language=result.language,
        source=source,
        duration=duration,
    )


class ElevenLabsSTT:
    """ElevenLabs Speech-to-Text provider."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def _client(self):
        return get_elevenlabs_client(self.settings)

    async def transcribe(self, audio: bytes, *, language: str | None = None) -> Transcript:
        """Transcribe audio bytes with diarization and word timestamps."""
        client = self._client()
        logger.info(
            "ElevenLabs STT request: model=%s diarize=true", self.settings.elevenlabs_stt_model
        )
        try:
            response = client.speech_to_text.convert(
                model_id=self.settings.elevenlabs_stt_model,
                file=audio,
                language_code=language,
                diarize=True,
                timestamps_granularity="word",
                tag_audio_events=True,
            )
        except Exception as exc:  # SDK raises typed errors; surface uniformly
            raise ElevenLabsError(f"ElevenLabs STT failed: {exc}") from exc

        chunk = getattr(response, "chunks", None)
        chunk = chunk[0] if chunk else response
        words = [dict(w) for w in (getattr(chunk, "words", None) or [])]
        result = STTResult(
            language=getattr(chunk, "language_code", None),
            language_probability=getattr(chunk, "language_probability", 0.0),
            audio_duration_secs=getattr(chunk, "audio_duration_secs", None),
            words=words,
        )
        return _words_to_transcript(result)

    async def transcribe_stream(self, audio: bytes, *, language: str | None = None):
        """Incremental transcription is not supported for file payloads.

        Returns a single transcript; realtime streaming is architecturally
        reserved for live mode (see docs/ARCHITECTURE.md).
        """
        yield await self.transcribe(audio, language=language)
