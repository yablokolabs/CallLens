"""Deterministic conversation metrics.

All functions here are pure and independently testable. They deliberately
contain no AI — everything that can be calculated reliably is calculated.
"""

from __future__ import annotations

import re

from calllens.domain.metrics import CallMetrics, SilenceGap, TalkRatio
from calllens.domain.transcript import SpeakerRole, Transcript, Utterance

# A silence is "real" only if it exceeds this threshold (seconds).
SILENCE_THRESHOLD = 0.5
# An utterance that starts while the previous speaker is still talking is an interruption.
INTERRUPTION_OVERLAP = 0.3

_WORD_RE = re.compile(r"\b[\w'’-]+\b")
_QUESTION_WORDS = {
    "what",
    "why",
    "how",
    "when",
    "where",
    "who",
    "which",
    "whose",
    "whom",
    "explain",
    "describe",
    "tell me",
}
_OPEN_QUESTION_MARKERS = (
    "what",
    "why",
    "how",
    "when",
    "where",
    "who",
    "which",
    "explain",
    "describe",
)


def count_words(text: str) -> int:
    return len(_WORD_RE.findall(text))


def _ends_with_question_mark(text: str) -> bool:
    return text.strip().endswith("?")


def classify_question(text: str) -> str | None:
    """Return 'open', 'closed', or None if the utterance is not a question."""
    lowered = text.lower().strip()
    is_question = _ends_with_question_mark(lowered) or any(
        lowered.startswith(w)
        for w in (
            "do ",
            "does ",
            "did ",
            "is ",
            "are ",
            "can ",
            "could ",
            "would ",
            "will ",
            "have ",
            "has ",
        )
    )
    if not is_question:
        return None
    first_words = " ".join(lowered.split()[:3])
    if any(marker in first_words for marker in _OPEN_QUESTION_MARKERS):
        return "open"
    if lowered.startswith(
        (
            "do ",
            "does ",
            "did ",
            "is ",
            "are ",
            "can ",
            "could ",
            "would ",
            "will ",
            "have ",
            "has ",
        )
    ):
        return "closed"
    return None


def _utterances_to_turns(utterances: list[Utterance]) -> list[list[Utterance]]:
    """Group consecutive utterances by the same speaker into turns."""
    turns: list[list[Utterance]] = []
    for u in utterances:
        if turns and turns[-1][-1].speaker_id == u.speaker_id:
            turns[-1].append(u)
        else:
            turns.append([u])
    return turns


def _speaker_side(speaker_id: str, roles: dict[str, SpeakerRole]) -> str:
    role = roles.get(speaker_id, SpeakerRole.UNKNOWN)
    if role == SpeakerRole.REPRESENTATIVE:
        return "representative"
    if role == SpeakerRole.CUSTOMER:
        return "customer"
    return "other"


def _duration(utterances: list[Utterance], fallback: float | None) -> float:
    ends = [u.end_time for u in utterances if u.end_time is not None]
    if ends:
        return max(ends)
    if fallback is not None:
        return fallback
    starts = [u.start_time for u in utterances if u.start_time is not None]
    return max(starts) if starts else 0.0


def compute_call_metrics(transcript: Transcript) -> CallMetrics:
    """Compute all deterministic metrics for a transcript."""
    utterances = transcript.utterances
    roles = transcript.speaker_roles()
    duration = _duration(utterances, transcript.duration)

    # Words and speaking time per side
    side_words = {"representative": 0, "customer": 0, "other": 0}
    side_time = {"representative": 0.0, "customer": 0.0, "other": 0.0}
    for u in utterances:
        side = _speaker_side(u.speaker_id, roles)
        side_words[side] += count_words(u.text)
        if u.end_time is not None:
            side_time[side] += max(0.0, u.end_time - u.start_time)

    total_words = sum(side_words.values())
    total_speech_time = sum(side_time.values())
    rep_time = side_time["representative"]
    cust_time = side_time["customer"]

    def _ratio(x: float) -> float:
        if total_speech_time <= 0:
            return 0.0
        return round(x / total_speech_time, 4)

    talk_ratio = TalkRatio(
        representative=_ratio(rep_time),
        customer=_ratio(cust_time),
        other=_ratio(side_time["other"]),
    )

    # Turns, transitions, interruptions
    turns = _utterances_to_turns(utterances)
    turn_count = len(turns)
    transitions = 0
    for prev_turn, cur_turn in zip(turns, turns[1:], strict=False):
        if prev_turn[-1].speaker_id != cur_turn[0].speaker_id:
            transitions += 1

    interruptions = 0
    for prev_u, cur_u in zip(utterances, utterances[1:], strict=False):
        if (
            prev_u.speaker_id != cur_u.speaker_id
            and prev_u.end_time is not None
            and cur_u.start_time < prev_u.end_time - INTERRUPTION_OVERLAP
        ):
            interruptions += 1

    # Silence gaps
    silence_gaps: list[SilenceGap] = []
    for prev_u, cur_u in zip(utterances, utterances[1:], strict=False):
        if prev_u.end_time is not None:
            gap = cur_u.start_time - prev_u.end_time
            if gap >= SILENCE_THRESHOLD:
                silence_gaps.append(
                    SilenceGap(start_time=prev_u.end_time, end_time=cur_u.start_time, duration=gap)
                )
    silence_duration = sum(g.duration for g in silence_gaps)

    # Longest monologue
    longest_monologue = 0.0
    longest_speaker: str | None = None
    for turn in turns:
        start = turn[0].start_time
        end = turn[-1].end_time if turn[-1].end_time is not None else start
        span = max(0.0, end - start)
        if span > longest_monologue:
            longest_monologue = span
            longest_speaker = turn[0].speaker_id

    # Questions (representative only is more useful for coaching, but we count all)
    question_count = 0
    open_question_count = 0
    for u in utterances:
        q = classify_question(u.text)
        if q is not None:
            question_count += 1
            if q == "open":
                open_question_count += 1

    avg_response_length = round(total_words / turn_count, 2) if turn_count else 0.0
    customer_rep_word_ratio = (
        round(cust_time / rep_time, 3) if rep_time > 0 else (1.0 if cust_time == 0 else 0.0)
    )
    words_per_minute = round(total_words / (duration / 60.0), 2) if duration > 0 else 0.0

    return CallMetrics(
        duration=round(duration, 3),
        total_words=total_words,
        words_per_minute=words_per_minute,
        representative_words=side_words["representative"],
        customer_words=side_words["customer"],
        representative_speaking_time=round(rep_time, 3),
        customer_speaking_time=round(cust_time, 3),
        talk_ratio=talk_ratio,
        turns=turn_count,
        speaker_transitions=transitions,
        interruptions=interruptions,
        silence_duration=round(silence_duration, 3),
        longest_monologue=round(longest_monologue, 3),
        longest_monologue_speaker=longest_speaker,
        avg_response_length_words=avg_response_length,
        customer_rep_word_ratio=customer_rep_word_ratio,
        question_count=question_count,
        open_question_count=open_question_count,
        silence_gaps=silence_gaps,
    )
