"""Rubric loading and parsing.

Rubrics are declarative YAML documents (see rubrics/consultative_sales.yaml).
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from calllens.domain.rubric import Rubric, RubricDimension


class RubricParseError(ValueError):
    """Raised when a rubric document is malformed."""


def parse_rubric(data: dict) -> Rubric:
    """Parse a rubric dict into a validated Rubric model."""
    try:
        dimensions = [
            RubricDimension(
                key=str(key),
                label=str(dim.get("label", key)),
                weight=float(dim["weight"]),
                description=str(dim.get("description", "")),
            )
            for key, dim in data.get("dimensions", {}).items()
        ]
        return Rubric(
            name=str(data["name"]),
            version=str(data["version"]),
            description=str(data.get("description", "")),
            dimensions=dimensions,
        )
    except (KeyError, TypeError, ValueError, ValidationError) as exc:
        raise RubricParseError(f"invalid rubric document: {exc}") from exc


def load_rubric(path: str | Path) -> Rubric:
    """Load and validate a rubric from a YAML file."""
    p = Path(path)
    try:
        raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise RubricParseError(f"cannot parse YAML at {p}: {exc}") from exc
    if not isinstance(raw, dict):
        raise RubricParseError(f"rubric at {p} must be a YAML mapping")
    return parse_rubric(raw)


def load_rubrics_from_dir(directory: str | Path) -> list[Rubric]:
    """Load every ``*.yaml`` rubric in a directory, sorted by name."""
    d = Path(directory)
    rubrics: list[Rubric] = []
    for path in sorted(d.glob("*.yaml")):
        rubrics.append(load_rubric(path))
    return rubrics
