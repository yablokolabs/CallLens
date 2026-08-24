"""Centralized configuration.

Model IDs and pipeline knobs live here — never scattered through application
logic. All secrets are read from the environment only.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """CallLens runtime configuration."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ── Speech provider ──────────────────────────────────────────────
    elevenlabs_api_key: str | None = None
    elevenlabs_stt_model: str = "scribe_v2"
    elevenlabs_tts_model: str = "eleven_multilingual_v3"
    elevenlabs_tts_voice_id: str = "JBFqnCBsd6RMkjVDRZzb"

    # ── Reasoning LLM provider ───────────────────────────────────────
    llm_provider: str = "mock"  # openai | anthropic | compatible | mock
    llm_model: str = "gpt-4o-mini"
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    compatible_base_url: str | None = None
    compatible_api_key: str | None = None
    llm_temperature: float = 0.1
    llm_max_tokens: int = 4096

    # ── Pipeline ─────────────────────────────────────────────────────
    confidence_threshold: float = 0.75
    max_rescore_attempts: int = 2
    langgraph_checkpoint: bool = True

    # ── App ──────────────────────────────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///./calllens.db"
    calls_analyze_sync: bool = False
    log_level: str = "INFO"
    # Directory holding bundled rubrics.
    rubrics_dir: Path = Path(__file__).resolve().parents[4] / "rubrics"

    @property
    def speech_enabled(self) -> bool:
        return bool(self.elevenlabs_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
