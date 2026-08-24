"""Shared fixtures.

Every test runs fully offline: mock speech + mock LLM providers only.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from calllens.config import Settings
from calllens.domain.transcript import Transcript
from calllens.providers.llm.mock import MockLLMProvider
from calllens.providers.speech.mock import MockSpeechProvider, sample_transcript
from calllens.rubrics.loader import load_rubric
from calllens.storage.memory import InMemoryRepository
from calllens.testing import build_mock_llm

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def settings() -> Settings:
    return Settings(
        llm_provider="mock",
        elevenlabs_api_key=None,
        langgraph_checkpoint=False,
        confidence_threshold=0.75,
        max_rescore_attempts=2,
        rubrics_dir=PROJECT_ROOT / "rubrics",
    )


@pytest.fixture
def rubric():
    return load_rubric(PROJECT_ROOT / "rubrics" / "consultative_sales.yaml")


@pytest.fixture
def transcript() -> Transcript:
    return sample_transcript()


@pytest.fixture
def mock_llm(transcript) -> MockLLMProvider:
    return build_mock_llm(transcript)


@pytest.fixture
def mock_speech(transcript) -> MockSpeechProvider:
    return MockSpeechProvider(transcript)


@pytest.fixture
def repository() -> InMemoryRepository:
    return InMemoryRepository()
