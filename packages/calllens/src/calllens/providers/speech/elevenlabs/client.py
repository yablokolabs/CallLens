"""Lazy ElevenLabs SDK client.

The SDK client is constructed lazily so the module imports cleanly in
environments without an API key (tests, CI).
"""

from __future__ import annotations

from functools import lru_cache

from calllens.config import Settings, get_settings


class ElevenLabsError(RuntimeError):
    """Raised for ElevenLabs provider failures."""


class ElevenLabsNotConfigured(ElevenLabsError):
    """Raised when ELEVENLABS_API_KEY is not set."""


@lru_cache
def _client_for_key(api_key: str) -> object:
    from elevenlabs import ElevenLabs as SDKClient

    return SDKClient(api_key=api_key)


def get_elevenlabs_client(settings: Settings | None = None) -> object:
    """Return a configured ElevenLabs client or raise if no API key is set."""
    settings = settings or get_settings()
    if not settings.elevenlabs_api_key:
        raise ElevenLabsNotConfigured(
            "ELEVENLABS_API_KEY is not set; configure it in the environment (.env)"
        )
    # Cache keyed on the API key (Settings is unhashable, so it cannot be
    # passed directly to lru_cache).
    return _client_for_key(settings.elevenlabs_api_key)
