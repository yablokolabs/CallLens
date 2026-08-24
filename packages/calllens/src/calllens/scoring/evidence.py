"""Candidate evidence extraction + deterministic verification.

Candidate evidence comes from the LLM; verification is deterministic — every
timestamp must resolve to a real utterance in the transcript. The excerpt is
always taken from the transcript itself, never from the LLM's quote.
"""

from __future__ import annotations

from dataclasses import dataclass

from calllens.domain.scoring import Evidence
from calllens.domain.transcript import SpeakerRole, Transcript, Utterance
from calllens.prompts import evidence_prompt
from calllens.providers.llm.base import LLMProvider
from calllens.semantic.schemas import EvidenceCandidate, EvidenceCandidates
from calllens.transcript.format import format_transcript

SNAP_WINDOW = 30.0  # seconds: how far a timestamp may snap to a real utterance


@dataclass
class VerificationResult:
    verified: list[Evidence]
    dropped: list[str]  # human-readable reasons for dropped candidates


def _utterance_at(utterances: list[Utterance], timestamp: float) -> Utterance | None:
    """Return the utterance containing the timestamp (with snap tolerance)."""
    best: Utterance | None = None
    best_gap = float("inf")
    for u in utterances:
        start = u.start_time
        end = u.end_time if u.end_time is not None else start
        if start <= timestamp <= end:
            return u
        gap = min(abs(timestamp - start), abs(timestamp - end))
        if gap < best_gap:
            best_gap = gap
            best = u
    if best is not None and best_gap <= SNAP_WINDOW:
        return best
    return None


def _role_for(speaker: str) -> SpeakerRole:
    return SpeakerRole.REPRESENTATIVE if speaker == "representative" else SpeakerRole.CUSTOMER


def verify_candidates(
    transcript: Transcript,
    candidates: list[EvidenceCandidate],
    kind: str,
) -> VerificationResult:
    """Map candidate timestamps onto real utterances and rebuild excerpts."""
    verified: list[Evidence] = []
    dropped: list[str] = []
    roles = transcript.speaker_roles()
    utterances = transcript.utterances

    for cand in candidates:
        utterance = _utterance_at(utterances, cand.start_time)
        if utterance is None:
            dropped.append(f"{cand.start_time:.1f}s: no utterance within {SNAP_WINDOW}s")
            continue
        expected_role = _role_for(cand.speaker)
        if roles.get(utterance.speaker_id, SpeakerRole.UNKNOWN) != expected_role:
            # Try to find a nearby utterance by the expected side before dropping.
            fallback = _nearest_by_role(utterances, cand.start_time, expected_role, roles)
            if fallback is None:
                dropped.append(
                    f"{cand.start_time:.1f}s: expected {expected_role.value}, "
                    f"found {utterance.speaker_id}"
                )
                continue
            utterance = fallback
        verified.append(
            Evidence(
                start_time=utterance.start_time,
                end_time=utterance.end_time,
                speaker_id=utterance.speaker_id,
                transcript_excerpt=utterance.text,
                explanation=cand.explanation,
                kind=kind,
            )
        )
    return VerificationResult(verified=verified, dropped=dropped)


def _nearest_by_role(
    utterances: list[Utterance],
    timestamp: float,
    role: SpeakerRole,
    roles: dict[str, SpeakerRole],
) -> Utterance | None:
    best: Utterance | None = None
    best_gap = float("inf")
    for u in utterances:
        if roles.get(u.speaker_id, SpeakerRole.UNKNOWN) != role:
            continue
        gap = abs(u.start_time - timestamp)
        if gap < best_gap:
            best_gap = gap
            best = u
    if best is not None and best_gap <= SNAP_WINDOW:
        return best
    return None


class EvidenceExtractor:
    """Stage 1: extract candidate evidence for a rubric dimension."""

    def __init__(self, llm: LLMProvider) -> None:
        self.llm = llm

    async def extract(
        self,
        transcript: Transcript,
        *,
        dimension_key: str,
        dimension_label: str,
        dimension_description: str,
    ) -> EvidenceCandidates:
        prompt = evidence_prompt(
            format_transcript(transcript),
            dimension_label,
            dimension_description,
        )
        out = await self.llm.structured_completion(prompt, EvidenceCandidates)
        assert isinstance(out, EvidenceCandidates)
        return out

    def verify(self, transcript: Transcript, candidates: EvidenceCandidates) -> VerificationResult:
        """Stage 2: deterministically verify the extracted candidates."""
        positive = verify_candidates(transcript, candidates.positive, kind="positive")
        negative = verify_candidates(transcript, candidates.negative, kind="negative")
        return VerificationResult(
            verified=positive.verified + negative.verified,
            dropped=positive.dropped + negative.dropped,
        )
