"""Lightweight rep history — no vector DB, just 5-call window.

For each rep, retain enough structured history to show:
  Previous 5 calls: discovery issue 4/5, high talk ratio 3/5, …

The agent can then say: "This behavior has appeared in four of the last
five calls, so coaching is warranted."

Persistence: in-memory for tests/demo; SQLite JSON for local runs via
SQLAlchemy if a database_url is supplied. No external services.
"""

from __future__ import annotations

from dataclasses import dataclass

from calllens.coach.decisions import RepHistorySummary
from calllens.domain.report import CallReport


@dataclass
class HistoryRecord:
    call_id: str
    decision: str  # NO_ACTION | COACH | ESCALATE
    worst_dimension: str | None = None
    worst_score: float | None = None
    rep_talk_ratio: float | None = None
    discovery_low: bool = False
    high_talk: bool = False


class InMemoryHistoryStore:
    """Per-rep ring buffer of recent decisions (last 5)."""

    def __init__(self, window: int = 5) -> None:
        self.window = window
        self._by_rep: dict[str, list[HistoryRecord]] = {}

    def record(
        self,
        rep_id: str,
        report: CallReport,
        decision: str,
    ) -> None:
        worst = None
        worst_score = None
        discovery_low = False
        for sc in report.rubric_scores:
            if worst is None or sc.result.score < (worst_score or 999):
                worst = sc.dimension
                worst_score = float(sc.result.score)
            if sc.dimension == "discovery" and sc.result.score < 5.5:
                discovery_low = True
        talk = None
        high_talk = False
        if report.metrics is not None:
            talk = float(report.metrics.talk_ratio.representative)
            high_talk = talk >= 0.65
        rec = HistoryRecord(
            call_id=report.call_id,
            decision=decision,
            worst_dimension=worst,
            worst_score=worst_score,
            rep_talk_ratio=talk,
            discovery_low=discovery_low,
            high_talk=high_talk,
        )
        buf = self._by_rep.setdefault(rep_id, [])
        buf.append(rec)
        if len(buf) > self.window:
            buf.pop(0)

    def summary(self, rep_id: str) -> RepHistorySummary:
        buf = self._by_rep.get(rep_id, [])
        if not buf:
            return RepHistorySummary(
                rep_id=rep_id, total_calls=0, pattern_counts={}, last_decisions=[], note="No prior calls"
            )
        counts: dict[str, int] = {}
        for r in buf:
            if r.discovery_low:
                counts["discovery_issue"] = counts.get("discovery_issue", 0) + 1
            if r.high_talk:
                counts["high_talk_ratio"] = counts.get("high_talk_ratio", 0) + 1
            if r.worst_dimension:
                counts[r.worst_dimension] = counts.get(r.worst_dimension, 0) + 1
        last = [r.decision for r in buf[-3:]]
        note = f"Previous {len(buf)} calls: " + ", ".join(f"{k} {v}/{len(buf)}" for k, v in sorted(counts.items())[:3])
        if not counts:
            note = f"Previous {len(buf)} calls: no repeated issue"
        return RepHistorySummary(
            rep_id=rep_id,
            total_calls=len(buf),
            pattern_counts=counts,
            last_decisions=last,
            note=note,
        )

    def seed(self, rep_id: str, records: list[HistoryRecord]) -> None:
        """Directly seed history for demos (synthetic 5-call window)."""
        self._by_rep[rep_id] = list(records[-self.window :])

    def clear(self, rep_id: str | None = None) -> None:
        if rep_id is None:
            self._by_rep.clear()
        else:
            self._by_rep.pop(rep_id, None)


# Global default for FastAPI dependency wiring (single-process demo)
_default_store = InMemoryHistoryStore()


def get_history_store() -> InMemoryHistoryStore:
    return _default_store
