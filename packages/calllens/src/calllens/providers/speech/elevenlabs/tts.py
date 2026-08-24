"""ElevenLabs Text-to-Speech integration (spoken coaching)."""

from __future__ import annotations

import logging

from calllens.config import Settings, get_settings
from calllens.providers.speech.elevenlabs.client import ElevenLabsError, get_elevenlabs_client

logger = logging.getLogger(__name__)


class ElevenLabsTTS:
    """Synthesizes speech audio from text (e.g. coaching recommendations)."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def _client(self):
        return get_elevenlabs_client(self.settings)

    async def synthesize(self, text: str) -> bytes:
        client = self._client()
        try:
            audio = client.text_to_speech.convert(
                text=text,
                voice_id=self.settings.elevenlabs_tts_voice_id,
                model_id=self.settings.elevenlabs_tts_model,
                output_format="mp3_44100_128",
            )
        except Exception as exc:
            raise ElevenLabsError(f"ElevenLabs TTS failed: {exc}") from exc
        return b"".join(audio)
