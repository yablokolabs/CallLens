"""Confidence calculation.

Final confidence combines the model's stated confidence with a deterministic
evidence-quality factor (how much of the extracted evidence survived
verification) and the consistency factor.
"""

from __future__ import annotations

from calllens.domain.scoring import Evidence


def evidence_coverage(verified: list[Evidence] | int, candidates_total: int) -> float:
    """Fraction of candidate evidence that survived verification.

    Accepts either the verified list or a plain count (tests).
    """
    if candidates_total <= 0:
        return 0.0
    verified_count = verified if isinstance(verified, int) else len(verified)
    return min(1.0, verified_count / candidates_total)


def calculate_confidence(
    model_confidence: float,
    *,
    verified_evidence: list[Evidence],
    candidate_count: int,
    consistency_factor: float,
) -> float:
    coverage = evidence_coverage(verified_evidence, candidate_count)
    evidence_factor = 0.5 + 0.5 * coverage
    confidence = model_confidence * evidence_factor * consistency_factor
    return round(min(1.0, max(0.0, confidence)), 4)
