"""Deterministic transcript formatting.

Transcripts can exceed LLM context windows, so we render a compact,
bounded representation with timestamps and speaker labels.
"""

from __future__ import annotations

from calllens.domain.transcript import SpeakerRole, Transcript, Utterance

ROLE_LABEL = {
    SpeakerRole.REPRESENTATIVE: "REPRESENTATIVE",
    SpeakerRole.CUSTOMER: "CUSTOMER",
    SpeakerRole.UNKNOWN: "SPEAKER",
}


def format_timestamp(seconds: float) -> str:
    """Format seconds as ``MM:SS`` (or ``H:MM:SS`` for long calls)."""
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _speaker_label(speaker_id: str, roles: dict[str, SpeakerRole]) -> str:
    role = roles.get(speaker_id, SpeakerRole.UNKNOWN)
    return f"{ROLE_LABEL[role]}({speaker_id})"


def format_transcript(transcript: Transcript, *, max_words: int = 6000) -> str:
    """Render a bounded, timestamped transcript for prompts."""
    roles = transcript.speaker_roles()
    lines: list[str] = []
    words = 0
    for u in transcript.utterances:
        if words >= max_words:
            lines.append("[... transcript truncated ...]")
            break
        words += len(u.text.split())
        lines.append(
            f"[{format_timestamp(u.start_time)}] {_speaker_label(u.speaker_id, roles)}: {u.text}"
        )
    return "\n".join(lines)


def transcript_excerpt(utterances: list[Utterance], start: float, end: float | None = None) -> str:
    """Join utterances overlapping [start, end] into a single excerpt."""
    end = end if end is not None else start + 15.0
    matching = [
        u.text for u in utterances if u.start_time <= end and (u.end_time or u.start_time) >= start
    ]
    return " ".join(matching).strip()
