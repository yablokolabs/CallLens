# ElevenLabs Integration

ElevenLabs is CallLens' primary **speech** provider. It is deliberately **not** the reasoning architecture — all semantic work goes through the separate `LLMProvider` abstraction.

## Verified API surface

This document reflects the ElevenLabs Python SDK as installed at development time (`elevenlabs>=2.40`; verified on **2.64.0**). Model IDs are centralized in `calllens/config.py` — never scattered through application logic.

| Setting | Default | Notes |
| --- | --- | --- |
| `ELEVENLABS_API_KEY` | — | from environment only |
| `ELEVENLABS_STT_MODEL` | `scribe_v2` | current recommended STT model (`scribe_v1` also accepted) |
| `ELEVENLABS_TTS_MODEL` | `eleven_multilingual_v3` | spoken coaching |
| `ELEVENLABS_TTS_VOICE_ID` | — | configured voice |

## Speech-to-text

`calllens/providers/speech/elevenlabs/stt.py` calls the current SDK surface:

```python
client.speech_to_text.convert(
    model_id="scribe_v2",
    file=audio_bytes,
    language_code=None,  # None → auto-detect (multilingual)
    diarize=True,
    timestamps_granularity="word",
    tag_audio_events=True,
)
```

The response carries word-level tokens with `start`, `end`, and `speaker_id`. CallLens groups consecutive words by speaker into `Utterance` objects (`_words_to_transcript`) and drops non-speech event tokens (e.g. `[laughter]`). Punctuation is re-attached without spaces.

### Error handling

- Missing key → `ElevenLabsNotConfigured` at client construction (lazy; the module imports cleanly without a key).
- Any SDK/transport failure → `ElevenLabsError` with the original message.
- Timeouts/retries: the SDK's own transport handles retries; the pipeline records failures and persists the call as `FAILED`.

## Text-to-speech

`calllens/providers/speech/elevenlabs/tts.py` powers optional spoken coaching:

```http
POST /api/v1/coaching/{call_id}/speech
```

```python
client.text_to_speech.convert(text=..., voice_id=..., model_id=..., output_format="mp3_44100_128")
```

TTS is deliberately **not** a blocker for the MVP.

## Provider abstraction

Business logic depends only on `SpeechProvider` (see `providers/speech/base.py`):

```python
class SpeechProvider(Protocol):
    async def transcribe(self, audio: bytes, *, language: str | None = None) -> Transcript: ...
    async def transcribe_stream(
        self, audio: bytes, *, language: str | None = None
    ) -> AsyncIterator[Transcript]: ...
    async def synthesize(self, text: str) -> bytes: ...
```

`get_speech_provider(settings)` returns the ElevenLabs implementation when a key is configured, and a deterministic `MockSpeechProvider` otherwise — so local development, tests, and CI never require a paid key. ElevenLabs objects never leak into core scoring logic.

## Multilingual

Scribe v2 auto-detects language (90+ languages); CallLens stores `detected_language` and the original-language transcript. If translation is added later, it is stored separately — original-language evidence is never replaced.
