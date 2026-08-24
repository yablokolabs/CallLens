"""Parse uploaded transcript payloads into domain Transcripts."""

from __future__ import annotations

import json
import re

from calllens.domain.transcript import Speaker, SpeakerRole, Transcript, Utterance


class TranscriptParseError(ValueError):
    """Raised when an uploaded transcript cannot be parsed."""


_REP_LABELS = {
    "rep",
    "reps",
    "representative",
    "representatives",
    "agent",
    "agents",
    "sales",
    "seller",
    "associate",
}
_CUST_LABELS = {
    "customer",
    "customers",
    "client",
    "clients",
    "buyer",
    "buyers",
    "prospect",
    "prospects",
    "caller",
    "guest",
}


def _infer_role(speaker_id: str) -> SpeakerRole:
    """Infer a speaker role from a recognizable speaker label."""
    label = speaker_id.lower().strip()
    if label in _REP_LABELS:
        return SpeakerRole.REPRESENTATIVE
    if label in _CUST_LABELS:
        return SpeakerRole.CUSTOMER
    return SpeakerRole.UNKNOWN


def _fill_roles(transcript: Transcript) -> Transcript:
    """Assign inferred roles to speakers that have none."""
    for speaker in transcript.speakers:
        if speaker.role == SpeakerRole.UNKNOWN:
            speaker.role = _infer_role(speaker.id)
    return transcript


def parse_transcript_json(raw: str) -> Transcript:
    """Parse a JSON transcript payload.

    Accepts either a full ``Transcript``-shaped object or a list of
    utterances with ``speaker_id``/``text``/``start_time``/``end_time``.
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise TranscriptParseError(f"invalid JSON transcript: {exc}") from exc

    if isinstance(data, list):
        utterances = [Utterance.model_validate(u) for u in data]
        speakers = _speakers_from_utterances(utterances)
        return Transcript(utterances=utterances, speakers=speakers, source="json")
    if isinstance(data, dict) and "utterances" in data:
        return _fill_roles(Transcript.model_validate(data))
    raise TranscriptParseError(
        "JSON transcript must be an object with 'utterances' or a list of utterances"
    )


def _speakers_from_utterances(utterances: list[Utterance]) -> list[Speaker]:
    ids = list(dict.fromkeys(u.speaker_id for u in utterances))
    return [Speaker(id=sid, role=_infer_role(sid)) for sid in ids]


_TIMESTAMP_RE = re.compile(
    r"\[?(\d{1,2}):(\d{2})(?::(\d{2}))?\]?\s*([A-Z_]+(?:\([^)]+\))?|SPEAKER[A-Z0-9_]*)?:?\s*(.*)",
    re.I,
)


def _to_seconds(h: str, m: str, s: str | None) -> float:
    """Convert timestamp groups to seconds.

    Two groups are ``MM:SS`` (the convention in call transcripts); three
    groups are ``H:MM:SS``.
    """
    if s is None:
        return int(h) * 60 + int(m)
    return int(h) * 3600 + int(m) * 60 + int(s)


def parse_transcript_text(raw: str) -> Transcript:
    """Parse a plain-text transcript.

    Supports lines like ``00:12 REP: Hello`` or ``[00:12] Customer: Hi``.
    Lines without a timestamp are appended to the previous utterance.
    """
    utterances: list[Utterance] = []
    current: Utterance | None = None
    cursor = 0.0

    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        match = _TIMESTAMP_RE.match(line)
        if match:
            h, m, sec, speaker, text = match.groups()
            start = _to_seconds(h, m, sec)
            speaker_id = (speaker or "unknown").lower().split("(")[0].strip() or "unknown"
            if current is not None:
                current.end_time = start
            current = Utterance(speaker_id=speaker_id, text=text, start_time=start)
            utterances.append(current)
            cursor = start
        elif current is not None:
            current.text = f"{current.text} {line}"
        else:
            current = Utterance(speaker_id="unknown", text=line, start_time=cursor)
            utterances.append(current)

    if not utterances:
        raise TranscriptParseError("text transcript contains no parseable lines")
    return Transcript(
        utterances=utterances, speakers=_speakers_from_utterances(utterances), source="text"
    )
