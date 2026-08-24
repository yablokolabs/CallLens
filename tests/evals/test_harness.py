"""Evaluation harness tests."""

from __future__ import annotations

import pytest

from calllens.evals.harness import EvaluationHarness
from calllens.evals.metrics import (
    correlation,
    f1_score,
    mean_absolute_error,
    precision_recall_f1,
    rmse,
)
from calllens.evals.synthetic import (
    EXPECTED_SCORES,
    SCENARIOS,
    generate_synthetic_dataset,
    list_scenarios,
)


def test_mae():
    assert mean_absolute_error([1, 2, 3], [1, 2, 3]) == 0.0
    assert mean_absolute_error([1, 2], [3, 4]) == 2.0
    assert mean_absolute_error([], []) == 0.0


def test_rmse():
    assert rmse([0, 0], [3, 4]) == pytest.approx(3.5355, abs=0.001)


def test_correlation_perfect():
    assert correlation([1, 2, 3, 4], [2, 4, 6, 8]) == pytest.approx(1.0)
    assert correlation([1, 2, 3], [3, 2, 1]) == pytest.approx(-1.0)


def test_correlation_constant_inputs():
    assert correlation([5, 5, 5], [1, 2, 3]) == 0.0


def test_precision_recall_f1():
    p, r, f = precision_recall_f1(10, 5, 5)
    assert p == pytest.approx(10 / 15)
    assert r == pytest.approx(10 / 15)
    assert f == pytest.approx(0.666, abs=0.001)
    assert f1_score(0, 0, 0) == 0.0


def test_scenarios_complete():
    scenarios = list_scenarios()
    assert len(scenarios) == 13
    for name in SCENARIOS:
        assert name in EXPECTED_SCORES


def test_generate_dataset():
    calls = generate_synthetic_dataset(scenarios=["short_call", "poor_salesperson"])
    assert len(calls) == 2
    assert calls[0].transcript.utterances
    assert calls[0].expected_scores["rapport"] > 0


@pytest.mark.asyncio
async def test_harness_runs_and_reports(settings, rubric):
    from calllens.evals.synthetic import generate_synthetic_dataset

    calls = generate_synthetic_dataset(scenarios=["excellent_salesperson", "poor_salesperson"])
    harness = EvaluationHarness(rubric)
    result = await harness.evaluate(calls)
    assert len(result.runs) == 2
    assert result.overall_mae >= 0
    assert "discovery" in result.dimensions
    markdown = result.to_markdown()
    assert "Overall MAE" in markdown
