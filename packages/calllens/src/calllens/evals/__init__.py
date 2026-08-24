"""Evaluation harness for scoring quality."""

from calllens.evals.harness import EvaluationHarness, EvaluationResult
from calllens.evals.metrics import (
    correlation,
    f1_score,
    mean_absolute_error,
    precision_recall_f1,
    rmse,
)
from calllens.evals.synthetic import generate_synthetic_dataset, list_scenarios

__all__ = [
    "EvaluationHarness",
    "EvaluationResult",
    "correlation",
    "f1_score",
    "generate_synthetic_dataset",
    "list_scenarios",
    "mean_absolute_error",
    "precision_recall_f1",
    "rmse",
]
