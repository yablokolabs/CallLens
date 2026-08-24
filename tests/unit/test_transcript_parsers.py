"""Transcript ingestion parser tests."""

from __future__ import annotations

import pytest

from calllens.ingest.parsers import (
    TranscriptParseError,
    parse_transcript_json,
    parse_transcript_text,
)


def test_parse_json_object():
    raw = (
        '{"utterances": [{"speaker_id": "rep", "text": "Hello", "start_time": 0.0, "end_time": 2.0}, '  # noqa: E501
        '{"speaker_id": "customer", "text": "Hi", "start_time": 2.5, "end_time": 3.5}], '
        '"speakers": [{"id": "rep"}, {"id": "customer"}], "source": "json"}'
    )
    transcript = parse_transcript_json(raw)
    assert len(transcript.utterances) == 2
    assert transcript.utterances[0].speaker_id == "rep"
    assert transcript.source == "json"


def test_parse_json_list():
    raw = '[{"speaker_id": "a", "text": "one", "start_time": 0, "end_time": 1}]'
    transcript = parse_transcript_json(raw)
    assert len(transcript.utterances) == 1
    assert transcript.speakers[0].id == "a"


def test_parse_json_invalid():
    with pytest.raises(TranscriptParseError):
        parse_transcript_json("{not json")
    with pytest.raises(TranscriptParseError):
        parse_transcript_json('{"foo": 1}')


def test_parse_text_timestamps():
    raw = "00:00 REP: Hello there\n00:05 CUSTOMER: Hi!\n00:10 REP: How are you?"
    transcript = parse_transcript_text(raw)
    assert len(transcript.utterances) == 3
    assert transcript.utterances[0].start_time == 0.0
    assert transcript.utterances[1].start_time == 5.0
    assert transcript.utterances[2].start_time == 10.0


def test_parse_text_continuation_lines():
    raw = "00:00 REP: First part\ncontinued here\n00:10 CUSTOMER: Next"
    transcript = parse_transcript_text(raw)
    assert len(transcript.utterances) == 2
    assert "continued here" in transcript.utterances[0].text


def test_parse_text_empty():
    with pytest.raises(TranscriptParseError):
        parse_transcript_text("")
