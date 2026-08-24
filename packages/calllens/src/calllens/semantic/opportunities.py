"""Opportunity and risk detection."""

from __future__ import annotations

from calllens.domain.opportunities import Opportunity, OpportunityType, Risk, RiskType
from calllens.domain.transcript import Transcript
from calllens.prompts import opportunities_prompt
from calllens.providers.llm.base import LLMProvider
from calllens.semantic.schemas import OpportunitiesOutput
from calllens.transcript.format import format_transcript


class OpportunityDetector:
    """Detects commercial opportunities and risks with evidence."""

    def __init__(self, llm: LLMProvider) -> None:
        self.llm = llm

    async def detect(self, transcript: Transcript) -> tuple[list[Opportunity], list[Risk]]:
        prompt = opportunities_prompt(format_transcript(transcript))
        out = await self.llm.structured_completion(prompt, OpportunitiesOutput)
        assert isinstance(out, OpportunitiesOutput)

        opportunities = [
            Opportunity(
                type=OpportunityType(o.type),
                confidence=o.confidence,
                description=o.description,
                product_context=o.product_context,
                evidence_timestamps=o.evidence_timestamps,
            )
            for o in out.opportunities
        ]
        risks = [
            Risk(
                type=RiskType(r.type),
                confidence=r.confidence,
                description=r.description,
                evidence_timestamps=r.evidence_timestamps,
            )
            for r in out.risks
        ]
        return opportunities, risks
