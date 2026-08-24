"""Rubric registry.

Seeded from the bundled ``rubrics/`` directory; custom rubrics can be added
at runtime (and, in production, persisted per organization).
"""

from __future__ import annotations

from pathlib import Path

from calllens.domain.rubric import Rubric
from calllens.rubrics.loader import load_rubrics_from_dir


class RubricRegistry:
    def __init__(self, rubrics_dir: str | Path) -> None:
        self._rubrics: dict[str, Rubric] = {}
        self._by_name: dict[str, Rubric] = {}
        if Path(rubrics_dir).exists():
            for rubric in load_rubrics_from_dir(rubrics_dir):
                self.register(rubric)

    def register(self, rubric: Rubric) -> None:
        self._rubrics[rubric.id] = rubric
        self._by_name[rubric.name] = rubric

    def get(self, name: str) -> Rubric | None:
        return self._by_name.get(name)

    def get_by_id(self, rubric_id: str) -> Rubric | None:
        return self._rubrics.get(rubric_id)

    def list(self) -> list[Rubric]:
        return sorted(self._rubrics.values(), key=lambda r: r.name)
