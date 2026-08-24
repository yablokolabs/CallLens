"""Topic and intent extraction."""

from __future__ import annotations

from calllens.domain.topics import Intent, Topic
from calllens.domain.transcript import Transcript
from calllens.prompts import intents_prompt, topics_prompt
from calllens.providers.llm.base import LLMProvider
from calllens.semantic.schemas import IntentOutput, TopicOutput
from calllens.transcript.format import format_transcript


class TopicExtractor:
    """Extracts structured topics with time windows."""

    def __init__(self, llm: LLMProvider) -> None:
        self.llm = llm

    async def extract(self, transcript: Transcript) -> list[Topic]:
        prompt = topics_prompt(format_transcript(transcript))
        out = await self.llm.structured_completion(prompt, TopicOutput)
        assert isinstance(out, TopicOutput)
        return sorted(out.topics, key=lambda t: t.start_time)


class IntentExtractor:
    """Detects conversational intents (objections, buying signals...)."""

    def __init__(self, llm: LLMProvider) -> None:
        self.llm = llm

    async def extract(self, transcript: Transcript) -> list[Intent]:
        prompt = intents_prompt(format_transcript(transcript))
        out = await self.llm.structured_completion(prompt, IntentOutput)
        assert isinstance(out, IntentOutput)
        return [
            Intent(
                type=i.type,
                description=i.description,
                confidence=i.confidence,
                evidence_timestamps=i.evidence_timestamps,
            )
            for i in out.intents
        ]
