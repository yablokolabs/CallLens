"""Multi-stage rubric scoring pipeline.

Stage flow per dimension:
  candidate evidence extraction (LLM)
  → deterministic evidence verification
  → rubric scoring (LLM, given verified evidence)
  → consistency check (deterministic)
  → confidence calculation (model × evidence quality × consistency)
  → bounded re-judge when confidence is below threshold

Never a single "score the transcript" prompt.
"""

from __future__ import annotations

import logging

from calllens.config import Settings, get_settings
from calllens.domain.rubric import Rubric, RubricDimension
from calllens.domain.scoring import RubricResult
from calllens.domain.transcript import Transcript
from calllens.prompts import rescore_prompt, score_prompt
from calllens.providers.llm.base import LLMProvider
from calllens.scoring.confidence import calculate_confidence
from calllens.scoring.consistency import check_consistency
from calllens.scoring.evidence import EvidenceExtractor
from calllens.semantic.schemas import DimensionScore, EvidenceCandidate, EvidenceCandidates
from calllens.transcript.format import format_transcript

logger = logging.getLogger(__name__)


class RubricScoringPipeline:
    """Scores a rubric against a transcript, dimension by dimension."""

    def __init__(
        self,
        llm: LLMProvider,
        settings: Settings | None = None,
    ) -> None:
        self.llm = llm
        self.settings = settings or get_settings()
        self.evidence_extractor = EvidenceExtractor(llm)

    async def score_rubric(self, rubric: Rubric, transcript: Transcript) -> list[RubricResult]:
        results: list[RubricResult] = []
        for dim in rubric.dimensions:
            result = await self._score_dimension(dim, transcript)
            results.append(result)
        return results

    async def _score_dimension(
        self,
        dim: RubricDimension,
        transcript: Transcript,
    ) -> RubricResult:
        candidates = await self.evidence_extractor.extract(
            transcript,
            dimension_key=dim.key,
            dimension_label=dim.label,
            dimension_description=dim.description,
        )
        verification = self.evidence_extractor.verify(transcript, candidates)
        verified = verification.verified
        positive = [e for e in verified if e.kind == "positive"]
        negative = [e for e in verified if e.kind == "negative"]

        score = await self._ask_for_score(dim, transcript, candidates)
        attempts = 0

        while attempts < self.settings.max_rescore_attempts:
            consistency = check_consistency(
                score.score,
                positive,
                negative,
                candidates.missing_behaviors,
            )
            confidence = calculate_confidence(
                score.confidence,
                verified_evidence=verified,
                candidate_count=len(candidates.positive) + len(candidates.negative),
                consistency_factor=consistency.factor,
            )
            if confidence >= self.settings.confidence_threshold:
                break
            attempts += 1
            logger.info(
                "Re-judging dimension=%s attempt=%d confidence=%.3f note=%s",
                dim.key,
                attempts,
                confidence,
                consistency.note,
            )
            score = await self._rescore(
                dim, transcript, score, consistency.instruction or consistency.note
            )

        final_consistency = check_consistency(
            score.score, positive, negative, candidates.missing_behaviors
        )
        final_confidence = calculate_confidence(
            score.confidence,
            verified_evidence=verified,
            candidate_count=len(candidates.positive) + len(candidates.negative),
            consistency_factor=final_consistency.factor,
        )

        return RubricResult(
            rubric_dimension=dim.key,
            score=round(score.score, 1),
            confidence=final_confidence,
            reasoning=score.reasoning,
            positive_evidence=positive,
            negative_evidence=negative,
            missing_behaviors=candidates.missing_behaviors,
            rescore_attempts=attempts,
        )

    async def _ask_for_score(
        self,
        dim: RubricDimension,
        transcript: Transcript,
        candidates: EvidenceCandidates,
    ) -> DimensionScore:
        positive = _render_evidence(candidates.positive)
        negative = _render_evidence(candidates.negative)
        prompt = score_prompt(
            format_transcript(transcript),
            dim.label,
            dim.description,
            positive,
            negative,
            "\n".join(f"- {b}" for b in candidates.missing_behaviors) or "(none)",
        )
        out = await self.llm.structured_completion(prompt, DimensionScore)
        assert isinstance(out, DimensionScore)
        return out

    async def _rescore(
        self,
        dim: RubricDimension,
        transcript: Transcript,
        previous: DimensionScore,
        instruction: str,
    ) -> DimensionScore:
        prompt = rescore_prompt(
            format_transcript(transcript),
            dim.label,
            previous.score,
            previous.reasoning,
            instruction,
        )
        out = await self.llm.structured_completion(prompt, DimensionScore)
        assert isinstance(out, DimensionScore)
        return out


def _render_evidence(items: list[EvidenceCandidate]) -> str:
    if not items:
        return "(none)"
    return "\n".join(
        f"- [{e.start_time:.1f}s] {e.transcript_excerpt} — {e.explanation}" for e in items
    )
