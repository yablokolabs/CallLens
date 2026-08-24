"""Rubric validation helpers."""

from __future__ import annotations

from calllens.domain.rubric import Rubric


def validate_rubric(rubric: Rubric) -> list[str]:
    """Return a list of human-readable issues; empty means valid."""
    issues: list[str] = []
    if not rubric.name.strip():
        issues.append("rubric name must not be empty")
    if not rubric.version.strip():
        issues.append("rubric version must not be empty")
    if not rubric.dimensions:
        issues.append("rubric must declare at least one dimension")
    total = sum(d.weight for d in rubric.dimensions)
    if abs(total - 1.0) > 1e-6:
        issues.append(f"dimension weights sum to {total:.4f}, expected 1.0")
    for dim in rubric.dimensions:
        if dim.weight <= 0 or dim.weight > 1:
            issues.append(f"dimension '{dim.key}' weight must be in (0, 1]")
        if not dim.label.strip():
            issues.append(f"dimension '{dim.key}' label must not be empty")
    return issues
