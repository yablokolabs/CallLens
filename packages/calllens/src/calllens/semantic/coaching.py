"""Evidence-backed coaching generation."""

from __future__ import annotations

from calllens.domain.coaching import CoachingInsight, CoachingPriority
from calllens.domain.scoring import RubricScore
from calllens.domain.transcript import Transcript
from calllens.prompts import coaching_prompt
from calllens.providers.llm.base import LLMProvider
from calllens.semantic.schemas import CoachingOutput
from calllens.transcript.format import format_transcript


def _summarize_scores(scores: list[RubricScore]) -> str:
    lines = []
    for s in scores:
        r = s.result
        lines.append(
            f"- {s.label} ({s.dimension}): {r.score:.1f}/10 "
            f"confidence {r.confidence:.2f} — {r.reasoning}"
        )
    return "\n".join(lines) or "(no scores)"


class CoachingGenerator:
    """Generates coaching recommendations that cite actual timestamps."""

    def __init__(self, llm: LLMProvider) -> None:
        self.llm = llm

    async def generate(
        self,
        transcript: Transcript,
        rubric_scores: list[RubricScore],
    ) -> list[CoachingInsight]:
        prompt = coaching_prompt(
            format_transcript(transcript),
            _summarize_scores(rubric_scores),
        )
        out = await self.llm.structured_completion(prompt, CoachingOutput)
        assert isinstance(out, CoachingOutput)
        return [
            CoachingInsight(
                title=c.title,
                priority=CoachingPriority(c.priority),
                recommendation=c.recommendation,
                rationale=c.rationale,
                evidence_timestamps=c.evidence_timestamps,
                suggested_phrasing=c.suggested_phrasing,
            )
            for c in out.recommendations
        ]
