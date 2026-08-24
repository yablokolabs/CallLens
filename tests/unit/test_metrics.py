"""Deterministic conversation metrics must be pure and exact."""

from __future__ import annotations

import pytest

from calllens.domain.transcript import Speaker, SpeakerRole, Transcript, Utterance
from calllens.metrics.conversation import classify_question, compute_call_metrics, count_words


def _transcript() -> Transcript:
    return Transcript(
        utterances=[
            Utterance(
                speaker_id="rep",
                text="Hi Sarah, thanks for taking the time.",
                start_time=0.0,
                end_time=3.0,
            ),
            Utterance(
                speaker_id="customer", text="Thanks for having me.", start_time=3.5, end_time=5.0
            ),
            Utterance(
                speaker_id="rep",
                text="What is your biggest bottleneck right now?",
                start_time=5.5,
                end_time=12.0,
            ),
            Utterance(
                speaker_id="customer",
                text="Fulfillment keeps missing SLA targets.",
                start_time=12.5,
                end_time=20.0,
            ),
            Utterance(
                speaker_id="rep",
                text="How much does that impact revenue?",
                start_time=21.0,
                end_time=26.0,
            ),
            Utterance(
                speaker_id="customer",
                text="We lost two accounts last quarter.",
                start_time=26.5,
                end_time=32.0,
            ),
        ],
        speakers=[
            Speaker(id="rep", role=SpeakerRole.REPRESENTATIVE),
            Speaker(id="customer", role=SpeakerRole.CUSTOMER),
        ],
        duration=32.0,
    )


def test_count_words():
    assert count_words("Hi there, world!") == 3
    assert count_words("") == 0


def test_question_classification():
    assert classify_question("What is your biggest bottleneck?") == "open"
    assert classify_question("How much does that impact revenue?") == "open"
    assert classify_question("Do you have a budget?") == "closed"
    assert classify_question("Is it expensive?") == "closed"
    assert classify_question("We lost two accounts.") is None


def test_talk_ratio_and_words():
    metrics = compute_call_metrics(_transcript())
    # rep: 3.0 + 6.5 + 5.0 = 14.5s; customer: 1.5 + 7.5 + 5.5 = 14.5s; total 29.0s
    assert metrics.talk_ratio.representative == round(14.5 / 29.0, 4)
    assert metrics.talk_ratio.customer == round(14.5 / 29.0, 4)
    assert metrics.total_words == 7 + 4 + 7 + 5 + 6 + 6
    assert metrics.representative_words == 7 + 7 + 6
    assert metrics.customer_words == 4 + 5 + 6


def test_turns_and_transitions():
    metrics = compute_call_metrics(_transcript())
    # 6 alternating utterances = 6 turns, 5 transitions
    assert metrics.turns == 6
    assert metrics.speaker_transitions == 5


def test_interruptions_detected():
    transcript = Transcript(
        utterances=[
            Utterance(
                speaker_id="rep",
                text="Let me explain something very important here",
                start_time=0.0,
                end_time=10.0,
            ),
            Utterance(speaker_id="customer", text="But wait—", start_time=3.0, end_time=5.0),
        ],
        speakers=[
            Speaker(id="rep", role=SpeakerRole.REPRESENTATIVE),
            Speaker(id="customer", role=SpeakerRole.CUSTOMER),
        ],
        duration=10.0,
    )
    metrics = compute_call_metrics(transcript)
    assert metrics.interruptions == 1


def test_silence_gaps():
    metrics = compute_call_metrics(_transcript())
    # Gaps >= 0.5s: 3.0→3.5, 5.0→5.5, 12.0→12.5, 20.0→21.0, 26.0→26.5
    assert metrics.silence_duration == pytest.approx(3.0, abs=0.01)
    assert len(metrics.silence_gaps) == 5


def test_longest_monologue():
    metrics = compute_call_metrics(_transcript())
    # Customer utterance 12.5→20.0 is the longest single turn (7.5s)
    assert metrics.longest_monologue == pytest.approx(7.5, abs=0.01)
    assert metrics.longest_monologue_speaker == "customer"


def test_questions_counted():
    metrics = compute_call_metrics(_transcript())
    assert metrics.question_count == 2
    assert metrics.open_question_count == 2


def test_wpm_and_word_ratio():
    metrics = compute_call_metrics(_transcript())
    assert metrics.words_per_minute == pytest.approx(metrics.total_words / (32.0 / 60.0), abs=0.01)
    assert metrics.customer_rep_word_ratio == pytest.approx(14.5 / 14.5, abs=0.001)


def test_empty_transcript():
    metrics = compute_call_metrics(Transcript(utterances=[], speakers=[], duration=0.0))
    assert metrics.turns == 0
    assert metrics.total_words == 0
    assert metrics.talk_ratio.representative == 0.0
    assert metrics.words_per_minute == 0.0
