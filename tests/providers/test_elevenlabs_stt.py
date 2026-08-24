"""ElevenLabs STT word→utterance grouping (pure, no network)."""

from __future__ import annotations

from calllens.providers.speech.elevenlabs.stt import STTResult, _words_to_transcript


def _words():
    return [
        {"text": "Hi", "start": 0.0, "end": 0.4, "type": "word", "speaker_id": "speaker_0"},
        {"text": "there", "start": 0.4, "end": 0.8, "type": "word", "speaker_id": "speaker_0"},
        {"text": "Hello", "start": 1.2, "end": 1.6, "type": "word", "speaker_id": "speaker_1"},
        {"text": "!", "start": 1.6, "end": 1.7, "type": "punctuation", "speaker_id": "speaker_1"},
        {
            "text": "[laughter]",
            "start": 2.0,
            "end": 2.4,
            "type": "event",
            "speaker_id": "speaker_0",
        },
    ]


def test_words_grouped_by_speaker():
    result = STTResult(language="en", words=_words())
    transcript = _words_to_transcript(result)
    assert len(transcript.utterances) == 2
    assert transcript.utterances[0].text == "Hi there"
    assert transcript.utterances[0].speaker_id == "speaker_0"
    assert transcript.utterances[0].start_time == 0.0
    assert transcript.utterances[1].text == "Hello!"
    assert transcript.utterances[1].speaker_id == "speaker_1"


def test_events_dropped():
    result = STTResult(words=_words())
    transcript = _words_to_transcript(result)
    texts = [u.text for u in transcript.utterances]
    assert all("laughter" not in t for t in texts)


def test_language_and_duration_carried():
    result = STTResult(
        language="de", language_probability=0.9, audio_duration_secs=5.0, words=_words()
    )
    transcript = _words_to_transcript(result)
    assert transcript.language == "de"
    assert transcript.duration == 5.0
    assert transcript.source == "elevenlabs"
