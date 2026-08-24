"""Rubric engine tests."""

from __future__ import annotations

from typing import Any

import pytest

from calllens.domain.rubric import Rubric, RubricDimension
from calllens.domain.scoring import RubricResult
from calllens.rubrics.engine import RubricEngine
from calllens.rubrics.loader import RubricParseError, load_rubric, parse_rubric
from calllens.rubrics.validator import validate_rubric

VALID_DOC: dict[str, Any] = {
    "name": "test_rubric",
    "version": "1.0",
    "dimensions": {
        "rapport": {"label": "Rapport", "weight": 0.5},
        "discovery": {"label": "Discovery", "weight": 0.5},
    },
}


def test_parse_valid_rubric():
    rubric = parse_rubric(VALID_DOC)
    assert rubric.name == "test_rubric"
    assert len(rubric.dimensions) == 2
    assert rubric.dimension("discovery") is not None


def test_parse_missing_name():
    with pytest.raises(RubricParseError):
        parse_rubric({"version": "1.0", "dimensions": {}})


def test_weights_must_sum_to_one():
    doc = dict(VALID_DOC)
    doc["dimensions"]["rapport"]["weight"] = 0.9
    with pytest.raises(ValueError, match="sum to 1.0"):
        parse_rubric(doc)


def test_duplicate_keys_rejected():
    with pytest.raises(ValueError, match="unique"):
        Rubric(
            name="x",
            version="1.0",
            dimensions=[
                RubricDimension(key="a", label="A", weight=0.5),
                RubricDimension(key="a", label="B", weight=0.5),
            ],
        )


def test_bundled_rubrics_validate(rubric):
    assert validate_rubric(rubric) == []
    assert len(rubric.dimensions) == 10
    weights = sum(d.weight for d in rubric.dimensions)
    assert weights == pytest.approx(1.0)


def test_load_rubric_file():
    rubric = load_rubric("rubrics/customer_support.yaml")
    assert rubric.name == "customer_support"
    assert validate_rubric(rubric) == []


def test_engine_overall_score(rubric):
    results = [
        RubricResult(
            rubric_dimension=d.key,
            score=8.0,
            confidence=0.9,
            reasoning="ok",
        )
        for d in rubric.dimensions
    ]
    engine = RubricEngine(rubric)
    assert engine.overall_score(results) == 80.0
    assert engine.weighted_confidence(results) == pytest.approx(0.9)


def test_engine_weights_matter(rubric):
    # Discovery has weight 0.16; rapport 0.08. A high discovery score should
    # move the total more than a high rapport score.
    base = [
        RubricResult(rubric_dimension=d.key, score=5.0, confidence=0.9, reasoning="")
        for d in rubric.dimensions
    ]
    high_discovery = [
        RubricResult(rubric_dimension="discovery", score=10.0, confidence=0.9, reasoning="")
    ]
    high_rapport = [
        RubricResult(rubric_dimension="rapport", score=10.0, confidence=0.9, reasoning="")
    ]
    engine = RubricEngine(rubric)
    delta_discovery = engine.overall_score(base + high_discovery) - engine.overall_score(base)
    delta_rapport = engine.overall_score(base + high_rapport) - engine.overall_score(base)
    assert delta_discovery > delta_rapport


def test_engine_build_scores(rubric):
    results = [
        RubricResult(rubric_dimension=d.key, score=7.0, confidence=0.8, reasoning="")
        for d in rubric.dimensions
    ]
    scores = RubricEngine(rubric).build_scores(results)
    assert len(scores) == 10
    assert scores[0].label == rubric.dimensions[0].label
    assert scores[0].weight == rubric.dimensions[0].weight
