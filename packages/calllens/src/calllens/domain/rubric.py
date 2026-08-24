"""Rubric domain models.

Rubrics are declarative and versioned so organizations can ship their own
behavioral standards without code changes.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class RubricDimension(BaseModel):
    """One scored behavioral dimension of a rubric."""

    key: str = Field(pattern=r"^[a-z0-9_]+$")
    label: str
    weight: float = Field(gt=0, le=1)
    description: str = ""


class Rubric(BaseModel):
    """A versioned, declarative behavioral rubric."""

    name: str
    version: str
    description: str = ""
    dimensions: list[RubricDimension]

    @model_validator(mode="after")
    def _weights_sum_to_one(self) -> Rubric:
        total = sum(d.weight for d in self.dimensions)
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"rubric weights must sum to 1.0, got {total:.4f}")
        keys = [d.key for d in self.dimensions]
        if len(set(keys)) != len(keys):
            raise ValueError("rubric dimension keys must be unique")
        return self

    def dimension(self, key: str) -> RubricDimension | None:
        return next((d for d in self.dimensions if d.key == key), None)

    @property
    def id(self) -> str:
        return f"{self.name}:{self.version}"
