"""Consistency checking.

Deterministic heuristics that detect tension between a proposed score and the
verified evidence. Returns a factor in [0.6, 1.0] and a human-readable note
used to drive the confidence gate and re-judge loop.
"""

from __future__ import annotations

from dataclasses import dataclass

from calllens.domain.scoring import Evidence


@dataclass
class ConsistencyResult:
    consistent: bool
    factor: float  # multiplier applied to model confidence
    note: str
    instruction: str | None = None  # prompt text for a re-judge, if needed


def check_consistency(
    score: float,
    positive: list[Evidence],
    negative: list[Evidence],
    missing_behaviors: list[str],
) -> ConsistencyResult:
    pos, neg = len(positive), len(negative)
    total = pos + neg

    # Not enough verified evidence to stand behind any score.
    if total == 0 and missing_behaviors:
        return ConsistencyResult(
            consistent=False,
            factor=0.6,
            note=(
                "No verified evidence and missing behaviors reported; score is weakly supported."
            ),
            instruction=(
                "Re-examine the transcript: is there really no observable "
                "behavior for this dimension?"
            ),
        )
    if total == 0:
        return ConsistencyResult(
            consistent=False,
            factor=0.7,
            note="No verified evidence found; confidence reduced.",
            instruction=(
                "Re-check the transcript and extract at least the most "
                "relevant moments for this dimension."
            ),
        )

    if score >= 7.0 and neg > pos:
        return ConsistencyResult(
            consistent=False,
            factor=0.65,
            note=(
                f"Score {score:.1f} is high but negative evidence ({neg}) "
                f"outweighs positive ({pos})."
            ),
            instruction="Reconsider the score: negative evidence outweighs positive evidence.",
        )
    if score <= 3.0 and pos > neg:
        return ConsistencyResult(
            consistent=False,
            factor=0.65,
            note=(
                f"Score {score:.1f} is low but positive evidence ({pos}) "
                f"outweighs negative ({neg})."
            ),
            instruction="Reconsider the score: positive evidence outweighs negative evidence.",
        )
    if score >= 9.0 and missing_behaviors:
        return ConsistencyResult(
            consistent=False,
            factor=0.85,
            note="Near-perfect score while missing behaviors were reported.",
            instruction="Reconcile the near-perfect score with the listed missing behaviors.",
        )

    # Mild quality penalty for heavy reliance on a single piece of evidence.
    factor = 0.95 if total == 1 else 1.0
    return ConsistencyResult(
        consistent=True,
        factor=factor,
        note="Score and evidence agree.",
    )
