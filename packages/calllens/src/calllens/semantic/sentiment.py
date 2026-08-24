"""Longitudinal sentiment analysis."""

from __future__ import annotations

from calllens.domain.sentiment import SentimentAnalysis, SpeakerSentiment, TurningPoint
from calllens.domain.transcript import Transcript
from calllens.prompts import sentiment_prompt
from calllens.providers.llm.base import LLMProvider
from calllens.semantic.schemas import SentimentOutput
from calllens.transcript.format import format_transcript


class SentimentAnalyzer:
    """Analyzes sentiment longitudinally, per speaker."""

    def __init__(self, llm: LLMProvider) -> None:
        self.llm = llm

    async def analyze(self, transcript: Transcript) -> SentimentAnalysis:
        prompt = sentiment_prompt(format_transcript(transcript))
        out = await self.llm.structured_completion(prompt, SentimentOutput)
        assert isinstance(out, SentimentOutput)

        def _speaker(data) -> SpeakerSentiment | None:
            if data is None:
                return None
            timeline = [seg for seg in (_segment(s) for s in data.timeline) if seg is not None]
            return SpeakerSentiment(
                speaker_id=data.speaker_id,
                timeline=timeline,
                overall=data.overall,
                average_score=data.average_score,
            )

        return SentimentAnalysis(
            customer=_speaker(out.customer),
            representative=_speaker(out.representative),
            turning_points=[TurningPoint(**tp.model_dump()) for tp in out.turning_points],
            engagement=out.engagement,
            frustration=out.frustration,
            enthusiasm=out.enthusiasm,
            uncertainty=out.uncertainty,
            objection_intensity=out.objection_intensity,
        )


def _segment(seg):
    from calllens.domain.sentiment import SentimentSegment

    return SentimentSegment(
        speaker_id=seg.speaker_id,
        start=seg.start,
        end=seg.end,
        sentiment=seg.sentiment,
        score=seg.score,
        confidence=seg.confidence,
    )
