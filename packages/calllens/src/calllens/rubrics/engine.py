"""Generic rubric scoring engine.

The engine is intentionally sales-agnostic: any rubric that validates can be
scored. Sales is just the first bundled rubric.
"""

from __future__ import annotations

from calllens.domain.rubric import Rubric
from calllens.domain.scoring import RubricResult, RubricScore


class RubricEngine:
    """Scores a rubric from per-dimension results and aggregates a total."""

    def __init__(self, rubric: Rubric) -> None:
        self.rubric = rubric

    def overall_score(self, results: list[RubricResult]) -> float:
        """Weighted average of dimension scores, scaled to 0-100."""
        by_key = {r.rubric_dimension: r for r in results}
        total = 0.0
        for dim in self.rubric.dimensions:
            result = by_key.get(dim.key)
            if result is not None:
                total += result.score * dim.weight
        return round(total * 10, 1)

    def build_scores(self, results: list[RubricResult]) -> list[RubricScore]:
        """Attach rubric metadata (label, weight) to each result."""
        by_key = {r.rubric_dimension: r for r in results}
        scores: list[RubricScore] = []
        for dim in self.rubric.dimensions:
            result = by_key.get(dim.key)
            if result is None:
                continue
            scores.append(
                RubricScore(
                    dimension=dim.key,
                    label=dim.label,
                    weight=dim.weight,
                    result=result,
                )
            )
        return scores

    def weighted_confidence(self, results: list[RubricResult]) -> float:
        by_key = {r.rubric_dimension: r for r in results}
        total = 0.0
        for dim in self.rubric.dimensions:
            result = by_key.get(dim.key)
            if result is not None:
                total += result.confidence * dim.weight
        return round(total, 4)
