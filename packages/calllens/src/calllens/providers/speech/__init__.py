"""Speech providers."""

from calllens.config import Settings, get_settings
from calllens.providers.speech.base import SpeechProvider
from calllens.providers.speech.mock import MockSpeechProvider


def get_speech_provider(
    settings: Settings | None = None, *, force_mock: bool = False
) -> SpeechProvider:
    """Return the configured speech provider.

    Falls back to the mock provider when no ElevenLabs key is configured —
    local development and CI must never require a paid API key.
    """
    settings = settings or get_settings()
    if force_mock or not settings.elevenlabs_api_key:
        return MockSpeechProvider()
    from calllens.providers.speech.elevenlabs.stt import ElevenLabsSTT
    from calllens.providers.speech.elevenlabs.tts import ElevenLabsTTS

    class _ElevenLabsProvider:
        def __init__(self) -> None:
            self._stt = ElevenLabsSTT(settings)
            self._tts = ElevenLabsTTS(settings)

        async def transcribe(self, audio: bytes, *, language: str | None = None):
            return await self._stt.transcribe(audio, language=language)

        async def transcribe_stream(self, audio: bytes, *, language: str | None = None):
            return self._stt.transcribe_stream(audio, language=language)

        async def synthesize(self, text: str) -> bytes:
            return await self._tts.synthesize(text)

    return _ElevenLabsProvider()


__all__ = ["MockSpeechProvider", "SpeechProvider", "get_speech_provider"]
