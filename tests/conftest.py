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


@pytest.fixture(autouse=True)
def _reset_coach_singleton():
    """Isolate Coach global between tests — avoids live .env (sarvam) leaking into mock tests."""
    import contextlib

    import calllens.coach.service as svc_mod
    from calllens.coach.history import get_history_store

    svc_mod._coach_service = None
    with contextlib.suppress(Exception):
        get_history_store().clear()
    yield
    svc_mod._coach_service = None
    with contextlib.suppress(Exception):
        get_history_store().clear()


@pytest.fixture
def settings() -> Settings:
    # _env_file=None prevents .env (which may have COACH_MODEL_PROVIDER=sarvam)
    # from polluting deterministic mock tests. Coach must be mock, not live.
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        llm_provider="mock",
        model_provider=None,
        coach_model_provider="mock",
        sarvam_api_key=None,
        compatible_api_key=None,
        openai_api_key=None,
        anthropic_api_key=None,
        elevenlabs_api_key=None,
        demo_mode=False,
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
