"""Evaluation metrics.

Pure functions, independently testable. Synthetic evaluation data is never
confused with production evidence.
"""

from __future__ import annotations

import math


def mean_absolute_error(actual: list[float], predicted: list[float]) -> float:
    if not actual:
        return 0.0
    return sum(abs(a - p) for a, p in zip(actual, predicted, strict=True)) / len(actual)


def rmse(actual: list[float], predicted: list[float]) -> float:
    if not actual:
        return 0.0
    return math.sqrt(
        sum((a - p) ** 2 for a, p in zip(actual, predicted, strict=True)) / len(actual)
    )


def correlation(actual: list[float], predicted: list[float]) -> float:
    """Pearson correlation; 0.0 when undefined (e.g. constant inputs)."""
    n = len(actual)
    if n < 2 or n != len(predicted):
        return 0.0
    ma = sum(actual) / n
    mp = sum(predicted) / n
    num = sum((a - ma) * (p - mp) for a, p in zip(actual, predicted, strict=True))
    den_a = math.sqrt(sum((a - ma) ** 2 for a in actual))
    den_p = math.sqrt(sum((p - mp) ** 2 for p in predicted))
    if den_a == 0 or den_p == 0:
        return 0.0
    return num / (den_a * den_p)


def precision_recall_f1(
    true_positives: int,
    false_positives: int,
    false_negatives: int,
) -> tuple[float, float, float]:
    precision = (
        true_positives / (true_positives + false_positives)
        if (true_positives + false_positives)
        else 0.0
    )
    recall = (
        true_positives / (true_positives + false_negatives)
        if (true_positives + false_negatives)
        else 0.0
    )
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return precision, recall, f1


def f1_score(true_positives: int, false_positives: int, false_negatives: int) -> float:
    return precision_recall_f1(true_positives, false_positives, false_negatives)[2]
