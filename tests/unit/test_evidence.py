"""Evidence verification + confidence pipeline tests."""

from __future__ import annotations

import pytest

from calllens.domain.scoring import Evidence
from calllens.domain.transcript import Speaker, SpeakerRole, Transcript, Utterance
from calllens.scoring.confidence import calculate_confidence, evidence_coverage
from calllens.scoring.consistency import check_consistency
from calllens.scoring.evidence import verify_candidates
from calllens.semantic.schemas import EvidenceCandidate


def _transcript() -> Transcript:
    return Transcript(
        utterances=[
            Utterance(
                speaker_id="rep",
                text="What is your biggest bottleneck?",
                start_time=5.5,
                end_time=12.0,
            ),
            Utterance(
                speaker_id="customer",
                text="Fulfillment misses SLA targets.",
                start_time=12.5,
                end_time=20.0,
            ),
            Utterance(
                speaker_id="rep",
                text="Our platform automates fulfillment.",
                start_time=21.0,
                end_time=30.0,
            ),
        ],
        speakers=[
            Speaker(id="rep", role=SpeakerRole.REPRESENTATIVE),
            Speaker(id="customer", role=SpeakerRole.CUSTOMER),
        ],
        duration=30.0,
    )


def test_verify_keeps_valid_candidates():
    transcript = _transcript()
    candidates = [
        EvidenceCandidate(
            start_time=5.5,
            speaker="representative",
            transcript_excerpt="?",
            explanation="discovery",
        ),
        EvidenceCandidate(
            start_time=12.5, speaker="customer", transcript_excerpt="?", explanation="context"
        ),
    ]
    result = verify_candidates(transcript, candidates, kind="positive")
    assert len(result.verified) == 2
    # Excerpt is rebuilt from the real transcript, never the LLM quote.
    assert result.verified[0].transcript_excerpt == "What is your biggest bottleneck?"
    assert result.verified[0].speaker_id == "rep"


def test_verify_snaps_nearby_timestamp():
    transcript = _transcript()
    candidates = [
        EvidenceCandidate(
            start_time=5.6, speaker="representative", transcript_excerpt="?", explanation="x"
        )
    ]
    result = verify_candidates(transcript, candidates, kind="positive")
    assert len(result.verified) == 1
    assert result.verified[0].start_time == 5.5


def test_verify_drops_far_timestamps():
    transcript = _transcript()
    candidates = [
        EvidenceCandidate(
            start_time=1000.0, speaker="representative", transcript_excerpt="?", explanation="x"
        )
    ]
    result = verify_candidates(transcript, candidates, kind="positive")
    assert len(result.verified) == 0
    assert len(result.dropped) == 1


def test_verify_switches_to_matching_side():
    transcript = _transcript()
    # Candidate claims "customer" but timestamp points at the rep utterance;
    # verifier should snap to the nearest customer utterance.
    candidates = [
        EvidenceCandidate(
            start_time=5.5, speaker="customer", transcript_excerpt="?", explanation="x"
        )
    ]
    result = verify_candidates(transcript, candidates, kind="negative")
    assert len(result.verified) == 1
    assert result.verified[0].speaker_id == "customer"
    assert result.verified[0].start_time == 12.5


def test_evidence_coverage():
    assert evidence_coverage(1, 0) == 0.0
    assert evidence_coverage(2, 4) == 0.5
    assert evidence_coverage(2, 2) == 1.0


def test_confidence_combines_factors():
    verified = [Evidence(start_time=1, speaker_id="rep", transcript_excerpt="x", explanation="y")]
    conf = calculate_confidence(
        0.9, verified_evidence=verified, candidate_count=2, consistency_factor=0.65
    )
    # 0.9 * (0.5 + 0.5*0.5) * 0.65 = 0.9 * 0.75 * 0.65 = 0.43875
    assert conf == pytest.approx(0.4388, abs=0.001)


def test_consistency_penalizes_mismatch():
    result = check_consistency(
        score=9.0,
        positive=[Evidence(start_time=1, speaker_id="r", transcript_excerpt="", explanation="")],
        negative=[],
        missing_behaviors=["never asked about budget"],
    )
    assert not result.consistent
    assert result.factor < 1.0
    assert result.instruction is not None


def test_consistency_penalizes_high_score_with_negative_evidence():
    neg = Evidence(start_time=1, speaker_id="r", transcript_excerpt="", explanation="")
    result = check_consistency(score=9.0, positive=[], negative=[neg, neg], missing_behaviors=[])
    assert not result.consistent


def test_consistency_ok_when_aligned():
    pos = Evidence(start_time=1, speaker_id="r", transcript_excerpt="", explanation="")
    result = check_consistency(score=8.0, positive=[pos, pos], negative=[], missing_behaviors=[])
    assert result.consistent
    assert result.factor == 1.0


def test_consistency_no_evidence_at_all():
    result = check_consistency(score=6.0, positive=[], negative=[], missing_behaviors=[])
    assert not result.consistent
    assert result.factor == 0.7
