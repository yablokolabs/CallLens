"""Mock speech provider.

Used in tests and local development without an ElevenLabs key. Never used to
produce production evidence — synthetic transcripts are clearly sourced.
"""

from __future__ import annotations

from calllens.domain.transcript import Speaker, Transcript, Utterance

SAMPLE_AUDIO = b"\x00\x01" * 64  # deterministic fake audio payload


def sample_transcript() -> Transcript:
    """A small, deterministic diarized conversation."""
    utterances = [
        Utterance(
            speaker_id="rep",
            text="Hi Sarah, thanks for taking the time today.",
            start_time=0.0,
            end_time=3.0,
        ),
        Utterance(
            speaker_id="customer", text="Thanks for having me.", start_time=3.5, end_time=5.0
        ),
        Utterance(
            speaker_id="rep",
            text="What is the biggest operational bottleneck your team is dealing with right now?",
            start_time=5.5,
            end_time=12.0,
        ),
        Utterance(
            speaker_id="customer",
            text="Our order fulfillment keeps missing SLA targets, and it is hurting renewals.",
            start_time=12.5,
            end_time=20.0,
        ),
        Utterance(
            speaker_id="rep",
            text="How much impact is that having on revenue?",
            start_time=21.0,
            end_time=25.0,
        ),
        Utterance(
            speaker_id="customer",
            text="We lost two enterprise accounts last quarter because of it.",
            start_time=25.5,
            end_time=30.0,
        ),
        Utterance(
            speaker_id="rep",
            text="That sounds serious. Our platform automates the fulfillment pipeline end to end.",
            start_time=31.0,
            end_time=40.0,
        ),
        Utterance(
            speaker_id="customer",
            text="Interesting. What does it cost?",
            start_time=41.0,
            end_time=43.0,
        ),
        Utterance(
            speaker_id="rep",
            text="Pricing starts at two thousand a month and scales with volume.",
            start_time=44.0,
            end_time=50.0,
        ),
    ]
    return Transcript(
        utterances=utterances,
        speakers=[
            Speaker(id="rep", label="Representative"),
            Speaker(id="customer", label="Customer"),
        ],
        source="mock",
        duration=50.0,
    )


class MockSpeechProvider:
    """Deterministic speech provider returning canned transcripts."""

    def __init__(self, transcript: Transcript | None = None) -> None:
        self._transcript = transcript or sample_transcript()

    async def transcribe(self, audio: bytes, *, language: str | None = None) -> Transcript:
        return self._transcript.model_copy(deep=True)

    async def transcribe_stream(self, audio: bytes, *, language: str | None = None):
        yield self._transcript.model_copy(deep=True)

    async def synthesize(self, text: str) -> bytes:
        return SAMPLE_AUDIO
