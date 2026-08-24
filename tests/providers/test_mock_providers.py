"""Mock provider behavior tests."""

from __future__ import annotations

import pytest

from calllens.providers.llm.errors import LLMOutputError
from calllens.providers.llm.mock import MockLLMProvider
from calllens.semantic.schemas import DimensionScore
from calllens.testing import build_mock_llm


@pytest.mark.asyncio
async def test_mock_speech_returns_transcript(mock_speech, transcript):
    result = await mock_speech.transcribe(b"audio")
    assert result == transcript
    assert await mock_speech.synthesize("hello") == b"\x00\x01" * 64


@pytest.mark.asyncio
async def test_mock_llm_registered_handler(mock_llm):
    out = await mock_llm.structured_completion("prompt", DimensionScore)
    assert isinstance(out, DimensionScore)
    assert 0 <= out.score <= 10


@pytest.mark.asyncio
async def test_mock_llm_default_instance_for_unknown_schema():
    llm = MockLLMProvider()
    from calllens.semantic.schemas import TopicOutput

    out = await llm.structured_completion("x", TopicOutput)
    assert isinstance(out, TopicOutput)


@pytest.mark.asyncio
async def test_mock_llm_rejects_wrong_type():
    llm = MockLLMProvider()

    def bad_handler(prompt, schema):
        return DimensionScore(dimension="x", score=5, confidence=0.5, reasoning="")

    from calllens.semantic.schemas import TopicOutput

    llm.register(TopicOutput, bad_handler)
    with pytest.raises(LLMOutputError):
        await llm.structured_completion("x", TopicOutput)


@pytest.mark.asyncio
async def test_build_mock_llm_with_unnormalized_transcript(transcript):
    llm = build_mock_llm(transcript)
    out = await llm.structured_completion("prompt", DimensionScore)
    assert isinstance(out, DimensionScore)


def test_speech_provider_factory_falls_back_to_mock(settings):
    from calllens.providers.speech import get_speech_provider

    provider = get_speech_provider(settings)
    assert isinstance(provider, object)
