"""ElevenLabs speech provider."""

from calllens.providers.speech.elevenlabs.client import ElevenLabsError, ElevenLabsNotConfigured
from calllens.providers.speech.elevenlabs.stt import ElevenLabsSTT
from calllens.providers.speech.elevenlabs.tts import ElevenLabsTTS

__all__ = [
    "ElevenLabsError",
    "ElevenLabsNotConfigured",
    "ElevenLabsSTT",
    "ElevenLabsTTS",
]
