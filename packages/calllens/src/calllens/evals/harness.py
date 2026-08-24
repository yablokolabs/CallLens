"""Evaluation harness.

Runs the full analysis pipeline (with mock providers) over a labeled dataset
and reports score quality: MAE, RMSE, correlation, and evidence
precision/recall against expected evidence timestamps.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from calllens.domain.rubric import Rubric
from calllens.evals.metrics import correlation, mean_absolute_error, precision_recall_f1, rmse
from calllens.evals.synthetic import SyntheticCall
from calllens.graphs import AnalysisGraph
from calllens.providers.llm.base import LLMProvider
from calllens.providers.speech.base import SpeechProvider
from calllens.testing import build_mock_llm


@dataclass
class DimensionReport:
    dimension: str
    mae: float = 0.0
    rmse: float = 0.0
    correlation: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    n: int = 0


@dataclass
class EvaluationResult:
    """Aggregate result of running the harness over a dataset."""

    runs: list[dict] = field(default_factory=list)
    dimensions: dict[str, DimensionReport] = field(default_factory=dict)
    overall_mae: float = 0.0
    overall_correlation: float = 0.0
    evidence_precision: float = 0.0
    evidence_recall: float = 0.0
    evidence_f1: float = 0.0

    def to_markdown(self) -> str:
        lines = [
            "| Dimension | MAE | Correlation | Precision | Recall | F1 |",
            "|---|---|---|---|---|---|",
        ]
        for dim, rep in sorted(self.dimensions.items()):
            lines.append(
                f"| {dim} | {rep.mae:.2f} | {rep.correlation:.2f} | "
                f"{rep.precision:.2f} | {rep.recall:.2f} | {rep.f1:.2f} |"
            )
        lines.append("")
        lines.append(f"Overall MAE: **{self.overall_mae:.3f}**")
        lines.append(f"Overall correlation: **{self.overall_correlation:.3f}**")
        lines.append(
            f"Evidence precision/recall/F1: **{self.evidence_precision:.3f} / "
            f"{self.evidence_recall:.3f} / {self.evidence_f1:.3f}**"
        )
        return "\n".join(lines)


class EvaluationHarness:
    """Runs the pipeline over synthetic/labeled conversations."""

    def __init__(
        self,
        rubric: Rubric,
        speech: SpeechProvider | None = None,
        llm: LLMProvider | None = None,
    ) -> None:
        self.rubric = rubric
        self.speech = speech
        self.llm = llm

    def _graph_for(self, call: SyntheticCall) -> AnalysisGraph:
        llm = self.llm or build_mock_llm(call.transcript)
        from calllens.providers.speech.mock import MockSpeechProvider

        speech = self.speech or MockSpeechProvider(call.transcript)
        from calllens.config import Settings

        return AnalysisGraph(
            speech=speech,
            llm=llm,
            settings=Settings(llm_provider="mock", langgraph_checkpoint=False),
            rubric=self.rubric,
        )

    async def evaluate(self, calls: list[SyntheticCall]) -> EvaluationResult:
        result = EvaluationResult()
        per_dim_actual: dict[str, list[float]] = {}
        per_dim_predicted: dict[str, list[float]] = {}
        expected_evidence: dict[str, list[float]] = {}
        found_evidence: dict[str, list[float]] = {}

        for call in calls:
            graph = self._graph_for(call)
            state = await graph.run(
                {
                    "call_id": call.call_id,
                    "transcript": call.transcript,
                    "rubric": self.rubric,
                    "rubric_name": self.rubric.name,
                }
            )
            report = state["final_report"]
            scores = {s.dimension: s.result for s in report.rubric_scores}

            run: dict = {"call_id": call.call_id, "scenario": call.scenario, "dimensions": {}}
            for dim, human in call.expected_scores.items():
                model = scores.get(dim)
                if model is None:
                    continue
                predicted = model.score
                per_dim_actual.setdefault(dim, []).append(float(human))
                per_dim_predicted.setdefault(dim, []).append(float(predicted))
                run["dimensions"][dim] = {"human": human, "predicted": predicted}
            result.runs.append(run)

            # Evidence quality: every expected dimension with a positive
            # model score should carry at least one verified piece of evidence.
            for dim, model in scores.items():
                expected_evidence.setdefault(dim, []).append(
                    1.0 if call.expected_scores.get(dim, 5) >= 5 else 0.0
                )
                found_evidence.setdefault(dim, []).append(
                    1.0 if len(model.positive_evidence) > 0 else 0.0
                )

        for dim in per_dim_actual:
            actual = per_dim_actual[dim]
            predicted = per_dim_predicted[dim]
            rep = DimensionReport(dimension=dim, n=len(actual))
            rep.mae = mean_absolute_error(actual, predicted)
            rep.rmse = rmse(actual, predicted)
            rep.correlation = correlation(actual, predicted)
            tp = sum(
                1
                for a, f in zip(expected_evidence[dim], found_evidence[dim], strict=True)
                if a == 1 and f == 1
            )
            fp = sum(
                1
                for a, f in zip(expected_evidence[dim], found_evidence[dim], strict=True)
                if a == 0 and f == 1
            )
            fn = sum(
                1
                for a, f in zip(expected_evidence[dim], found_evidence[dim], strict=True)
                if a == 1 and f == 0
            )
            rep.precision, rep.recall, rep.f1 = precision_recall_f1(tp, fp, fn)
            result.dimensions[dim] = rep

        all_actual = [v for vals in per_dim_actual.values() for v in vals]
        all_predicted = [v for vals in per_dim_predicted.values() for v in vals]
        result.overall_mae = mean_absolute_error(all_actual, all_predicted)
        result.overall_correlation = correlation(all_actual, all_predicted)

        tp = sum(
            1
            for dim in expected_evidence
            for a, f in zip(expected_evidence[dim], found_evidence[dim], strict=True)
            if a == 1 and f == 1
        )
        fp = sum(
            1
            for dim in expected_evidence
            for a, f in zip(expected_evidence[dim], found_evidence[dim], strict=True)
            if a == 0 and f == 1
        )
        fn = sum(
            1
            for dim in expected_evidence
            for a, f in zip(expected_evidence[dim], found_evidence[dim], strict=True)
            if a == 1 and f == 0
        )
        result.evidence_precision, result.evidence_recall, result.evidence_f1 = precision_recall_f1(
            tp, fp, fn
        )
        return result


def load_label_dataset(path: str | Path) -> list[dict]:
    """Load JSONL human-label records."""
    records = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records
