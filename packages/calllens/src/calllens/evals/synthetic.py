"""Synthetic evaluation data.

Generates realistic transcripts for the scenarios listed in the spec
(excellent seller, poor seller, weak discovery, ...). Each scenario ships a
human-quality label: per-dimension expected scores for the default rubric.

Synthetic data is for tests and evals only — never production evidence.
"""

from __future__ import annotations

import json
import random
from collections.abc import Sequence
from dataclasses import dataclass

from calllens.domain.transcript import Speaker, SpeakerRole, Transcript, Utterance

SCENARIOS = [
    "excellent_salesperson",
    "poor_salesperson",
    "weak_discovery",
    "excessive_talking",
    "aggressive_salesperson",
    "strong_rapport_no_close",
    "customer_objection",
    "angry_customer",
    "upsell_opportunity",
    "ambiguous_conversation",
    "short_call",
    "poor_transcription",
    "multilingual",
]

RUBRIC_DIMENSIONS = [
    "rapport",
    "credentialization",
    "ecosystem",
    "discovery",
    "adaptability",
    "adjacent_cross_sell",
    "future_cross_sell",
    "upsell",
    "customer_energy",
    "budget_alignment",
]

# Expected scores (0-10) per scenario for the consultative_sales rubric.
EXPECTED_SCORES: dict[str, dict[str, float]] = {
    "excellent_salesperson": {
        "rapport": 9,
        "credentialization": 8,
        "ecosystem": 8,
        "discovery": 9,
        "adaptability": 9,
        "adjacent_cross_sell": 8,
        "future_cross_sell": 7,
        "upsell": 7,
        "customer_energy": 9,
        "budget_alignment": 8,
    },
    "poor_salesperson": {
        "rapport": 3,
        "credentialization": 3,
        "ecosystem": 2,
        "discovery": 2,
        "adaptability": 2,
        "adjacent_cross_sell": 1,
        "future_cross_sell": 1,
        "upsell": 1,
        "customer_energy": 3,
        "budget_alignment": 2,
    },
    "weak_discovery": {
        "rapport": 7,
        "credentialization": 6,
        "ecosystem": 5,
        "discovery": 2,
        "adaptability": 4,
        "adjacent_cross_sell": 4,
        "future_cross_sell": 3,
        "upsell": 3,
        "customer_energy": 6,
        "budget_alignment": 4,
    },
    "excessive_talking": {
        "rapport": 5,
        "credentialization": 6,
        "ecosystem": 5,
        "discovery": 3,
        "adaptability": 3,
        "adjacent_cross_sell": 4,
        "future_cross_sell": 4,
        "upsell": 4,
        "customer_energy": 4,
        "budget_alignment": 3,
    },
    "aggressive_salesperson": {
        "rapport": 3,
        "credentialization": 6,
        "ecosystem": 4,
        "discovery": 3,
        "adaptability": 2,
        "adjacent_cross_sell": 6,
        "future_cross_sell": 5,
        "upsell": 7,
        "customer_energy": 2,
        "budget_alignment": 3,
    },
    "strong_rapport_no_close": {
        "rapport": 9,
        "credentialization": 6,
        "ecosystem": 5,
        "discovery": 7,
        "adaptability": 7,
        "adjacent_cross_sell": 5,
        "future_cross_sell": 4,
        "upsell": 3,
        "customer_energy": 8,
        "budget_alignment": 4,
    },
    "customer_objection": {
        "rapport": 6,
        "credentialization": 6,
        "ecosystem": 5,
        "discovery": 6,
        "adaptability": 7,
        "adjacent_cross_sell": 4,
        "future_cross_sell": 4,
        "upsell": 3,
        "customer_energy": 5,
        "budget_alignment": 5,
    },
    "angry_customer": {
        "rapport": 7,
        "credentialization": 5,
        "ecosystem": 4,
        "discovery": 6,
        "adaptability": 8,
        "adjacent_cross_sell": 3,
        "future_cross_sell": 2,
        "upsell": 2,
        "customer_energy": 6,
        "budget_alignment": 3,
    },
    "upsell_opportunity": {
        "rapport": 7,
        "credentialization": 7,
        "ecosystem": 6,
        "discovery": 7,
        "adaptability": 7,
        "adjacent_cross_sell": 8,
        "future_cross_sell": 7,
        "upsell": 8,
        "customer_energy": 7,
        "budget_alignment": 6,
    },
    "ambiguous_conversation": {
        "rapport": 5,
        "credentialization": 4,
        "ecosystem": 4,
        "discovery": 4,
        "adaptability": 4,
        "adjacent_cross_sell": 3,
        "future_cross_sell": 3,
        "upsell": 3,
        "customer_energy": 4,
        "budget_alignment": 3,
    },
    "short_call": {
        "rapport": 6,
        "credentialization": 4,
        "ecosystem": 3,
        "discovery": 5,
        "adaptability": 4,
        "adjacent_cross_sell": 2,
        "future_cross_sell": 2,
        "upsell": 2,
        "customer_energy": 5,
        "budget_alignment": 3,
    },
    "poor_transcription": {
        "rapport": 4,
        "credentialization": 3,
        "ecosystem": 3,
        "discovery": 4,
        "adaptability": 3,
        "adjacent_cross_sell": 2,
        "future_cross_sell": 2,
        "upsell": 2,
        "customer_energy": 4,
        "budget_alignment": 2,
    },
    "multilingual": {
        "rapport": 7,
        "credentialization": 6,
        "ecosystem": 5,
        "discovery": 7,
        "adaptability": 6,
        "adjacent_cross_sell": 4,
        "future_cross_sell": 4,
        "upsell": 4,
        "customer_energy": 6,
        "budget_alignment": 5,
    },
}


def list_scenarios() -> list[str]:
    return list(SCENARIOS)


@dataclass
class SyntheticCall:
    """A generated transcript plus its human-quality labels."""

    call_id: str
    scenario: str
    transcript: Transcript
    expected_scores: dict[str, float]

    def to_label_record(self) -> dict:
        """The human-label record format used by the evaluation dataset."""
        return {
            "call_id": self.call_id,
            "scenario": self.scenario,
            "dimension_scores": [
                {"dimension": dim, "human_score": score}
                for dim, score in self.expected_scores.items()
            ],
        }


def _u(speaker: str, text: str, t: float, dur: float | int) -> Utterance:
    return Utterance(speaker_id=speaker, text=text, start_time=t, end_time=t + float(dur))


def _make_transcript(
    lines: Sequence[tuple[str, str, float, float | int]], source: str = "synthetic"
) -> Transcript:
    utterances = [_u(*line) for line in lines]
    return Transcript(
        utterances=utterances,
        speakers=[
            Speaker(id="rep", label="Representative", role=SpeakerRole.REPRESENTATIVE),
            Speaker(id="customer", label="Customer", role=SpeakerRole.CUSTOMER),
        ],
        source=source,
        duration=max(u.end_time or 0 for u in utterances),
    )


def _tick(t: float, dur: float = 6.0) -> float:
    return t + dur + 0.5


def generate_scenario(scenario: str, seed: int = 0) -> SyntheticCall:
    """Generate one transcript for a named scenario."""
    t = 0.0
    if scenario == "excellent_salesperson":
        lines = [
            ("rep", "Hi Maya, great to meet you. How's your week going?", t := _tick(t), 4),
            ("customer", "Busy but good, thanks for asking.", t := _tick(t), 3),
            (
                "rep",
                "I'd love to understand what's driving you to look at this now.",
                t := _tick(t),
                5,
            ),
            (
                "customer",
                "Our onboarding is manual and it's slowing down new clients.",
                t := _tick(t),
                5,
            ),
            ("rep", "What's that costing you in time-to-value?", t := _tick(t), 4),
            ("customer", "Roughly two weeks per client, and it hurts retention.", t := _tick(t), 5),
            (
                "rep",
                "That's a real revenue impact. Let me show how we cut that to days.",
                t := _tick(t),
                6,
            ),
            ("customer", "That would be huge for us.", t := _tick(t), 3),
            ("rep", "We also integrate with your CRM and analytics stack.", t := _tick(t), 5),
            ("customer", "I like that. What does pricing look like?", t := _tick(t), 4),
            ("rep", "Plans start at two thousand a month and scale with usage.", t := _tick(t), 5),
            ("customer", "That fits our budget for this quarter.", t := _tick(t), 4),
            ("rep", "Let's schedule a pilot next week then.", t := _tick(t), 4),
        ]
    elif scenario == "poor_salesperson":
        lines = [
            ("rep", "So anyway our product is the best, everyone says so.", t := _tick(t), 5),
            ("customer", "Okay... what does it do exactly?", t := _tick(t), 4),
            ("rep", "It does everything. We have over a thousand features.", t := _tick(t), 5),
            ("customer", "I see. We were hoping to discuss our specific needs.", t := _tick(t), 5),
            (
                "rep",
                "Trust me, it'll handle whatever you need. When can we sign?",
                t := _tick(t),
                5,
            ),
            ("customer", "We're not ready to commit to anything today.", t := _tick(t), 4),
        ]
    elif scenario == "weak_discovery":
        lines = [
            ("rep", "Hi there! So, let me show you our platform right away.", t := _tick(t), 5),
            (
                "customer",
                "Actually, I had some questions about our situation first.",
                t := _tick(t),
                5,
            ),
            ("rep", "Sure, but the demo will answer most of them. Watch this.", t := _tick(t), 6),
            ("customer", "What problems does it solve for a company like ours?", t := _tick(t), 5),
            ("rep", "All of them, really. Here's the dashboard.", t := _tick(t), 5),
            ("customer", "Hmm. Do you know anything about our industry?", t := _tick(t), 4),
            ("rep", "We serve everyone. Let me show you the reporting module.", t := _tick(t), 5),
        ]
    elif scenario == "excessive_talking":
        lines = [
            (
                "rep",
                "Let me tell you about our journey, our founders, our funding...",
                t := _tick(t),
                20,
            ),
            (
                "rep",
                "And then we expanded into three more verticals with a new platform...",
                t := _tick(t),
                20,
            ),
            (
                "rep",
                "The architecture is microservices-based with a control plane...",
                t := _tick(t),
                20,
            ),
            (
                "customer",
                "Sorry to interrupt — what would this do for my team specifically?",
                t := _tick(t),
                5,
            ),
            (
                "rep",
                "Great question. First, let me give you some background on our pricing models...",
                t := _tick(t),
                20,
            ),
            ("customer", "I really need to keep this short.", t := _tick(t), 4),
        ]
    elif scenario == "aggressive_salesperson":
        lines = [
            ("rep", "You need our product. Your competitors already bought it.", t := _tick(t), 5),
            ("customer", "We haven't fully evaluated our options yet.", t := _tick(t), 5),
            ("rep", "There's no time for that. We can close this today.", t := _tick(t), 4),
            ("customer", "That's not how we make decisions.", t := _tick(t), 4),
            (
                "rep",
                "Look, I'll add the premium package and we'll sign right now.",
                t := _tick(t),
                5,
            ),
            ("customer", "I think we should end this call.", t := _tick(t), 4),
        ]
    elif scenario == "strong_rapport_no_close":
        lines = [
            ("rep", "How was your daughter's soccer game this weekend?", t := _tick(t), 4),
            ("customer", "She scored twice! We were thrilled.", t := _tick(t), 4),
            ("rep", "That's fantastic. You must be so proud.", t := _tick(t), 4),
            ("customer", "I really enjoy talking with you.", t := _tick(t), 3),
            ("rep", "So, anything I can help with this quarter?", t := _tick(t), 4),
            ("customer", "Not right now, but I'll keep you in mind.", t := _tick(t), 4),
            ("rep", "Absolutely, I'm always here if you need anything.", t := _tick(t), 4),
        ]
    elif scenario == "customer_objection":
        lines = [
            ("rep", "How are things going with your current provider?", t := _tick(t), 4),
            (
                "customer",
                "Honestly, we're locked into a two-year contract with them.",
                t := _tick(t),
                5,
            ),
            ("rep", "That's a common situation. When does it expire?", t := _tick(t), 4),
            ("customer", "In eighteen months. It feels like a long time.", t := _tick(t), 4),
            ("rep", "Understood. Many customers start with a pilot in parallel.", t := _tick(t), 5),
            ("customer", "That could work, but budgets are tight this year.", t := _tick(t), 4),
            (
                "rep",
                "A small pilot might fit within your existing spend. Shall we explore?",
                t := _tick(t),
                5,
            ),
        ]
    elif scenario == "angry_customer":
        lines = [
            (
                "customer",
                "Your product has been down for three days. This is unacceptable.",
                t := _tick(t),
                6,
            ),
            (
                "rep",
                "I hear you, and I'm sorry. Let me get to the bottom of this right now.",
                t := _tick(t),
                6,
            ),
            ("customer", "We've lost real revenue because of you.", t := _tick(t), 4),
            (
                "rep",
                "That's completely fair. Let's fix it and prevent recurrence.",
                t := _tick(t),
                5,
            ),
            ("customer", "I need a concrete timeline.", t := _tick(t), 4),
            (
                "rep",
                "You'll have a fix within 24 hours and a written root-cause report.",
                t := _tick(t),
                6,
            ),
        ]
    elif scenario == "upsell_opportunity":
        lines = [
            ("rep", "How's the basic plan working for you?", t := _tick(t), 4),
            ("customer", "Great, but we're hitting the usage limits every week.", t := _tick(t), 5),
            ("rep", "That's a great sign — it means you're getting real value.", t := _tick(t), 4),
            ("customer", "We'd need more seats and higher limits.", t := _tick(t), 4),
            (
                "rep",
                "The growth plan covers both, and adds analytics you'd likely use.",
                t := _tick(t),
                6,
            ),
            ("customer", "What's the delta in price?", t := _tick(t), 4),
            (
                "rep",
                "About forty percent more, but it removes every limit you hit.",
                t := _tick(t),
                5,
            ),
        ]
    elif scenario == "ambiguous_conversation":
        lines = [
            ("rep", "So, uh, we could maybe help with some of that, possibly.", t := _tick(t), 5),
            ("customer", "I'm not entirely sure what you're offering.", t := _tick(t), 4),
            ("rep", "Well, it depends on what you need, I guess.", t := _tick(t), 4),
            ("customer", "Do you have any case studies?", t := _tick(t), 4),
            ("rep", "I think we do. I can send something over, maybe.", t := _tick(t), 5),
        ]
    elif scenario == "short_call":
        lines = [
            ("rep", "Hi, this is Alex from Acme. Is now a good time?", t := _tick(t), 4),
            ("customer", "I only have five minutes.", t := _tick(t), 3),
            ("rep", "Understood. What's the one thing you'd want to solve?", t := _tick(t), 4),
            ("customer", "Faster reporting. That's it.", t := _tick(t), 3),
            ("rep", "We can demo that. Can we book twenty minutes next week?", t := _tick(t), 4),
            ("customer", "Sure, send me an invite.", t := _tick(t), 3),
        ]
    elif scenario == "poor_transcription":
        lines = [
            ("rep", "[inaudible] the platform [noise] handles everything", t := _tick(t), 5),
            ("customer", "hmm ... what [overlapping speech] mean?", t := _tick(t), 4),
            ("rep", "you know ... the thing ... [crosstalk]", t := _tick(t), 4),
            ("customer", "okay?", t := _tick(t), 2),
            ("rep", "[laughs] we can circle back", t := _tick(t), 3),
        ]
    elif scenario == "multilingual":
        lines = [
            ("rep", "Bonjour, merci de prendre le temps aujourd'hui.", t := _tick(t), 4),
            ("customer", "Avec plaisir. Nous avons des problèmes de livraison.", t := _tick(t), 5),
            ("rep", "Quel est l'impact sur votre chiffre d'affaires ?", t := _tick(t), 5),
            ("customer", "Environ dix pour cent de perte chaque trimestre.", t := _tick(t), 5),
            ("rep", "Notre solution automatise le processus de bout en bout.", t := _tick(t), 6),
            ("customer", "Cela semble intéressant. Quel est le prix ?", t := _tick(t), 4),
        ]
    else:  # pragma: no cover - defensive
        raise ValueError(f"unknown scenario: {scenario}")

    transcript = _make_transcript(lines)
    rng = random.Random(seed)
    expected = EXPECTED_SCORES[scenario]
    # Slight deterministic jitter so datasets aren't perfectly self-consistent.
    expected = {k: min(10.0, max(1.0, v + rng.choice([-0.5, 0, 0.5]))) for k, v in expected.items()}
    return SyntheticCall(
        call_id=f"synthetic-{scenario}-{seed}",
        scenario=scenario,
        transcript=transcript,
        expected_scores=expected,
    )


def generate_synthetic_dataset(
    scenarios: list[str] | None = None, seed: int = 0
) -> list[SyntheticCall]:
    """Generate one transcript per scenario (optionally a subset)."""
    names = scenarios or SCENARIOS
    return [generate_scenario(name, seed=seed) for name in names]


def write_label_dataset(calls: list[SyntheticCall], path: str) -> None:
    """Persist human-label records as JSONL."""
    with open(path, "w", encoding="utf-8") as fh:
        for call in calls:
            fh.write(json.dumps(call.to_label_record()) + "\n")
