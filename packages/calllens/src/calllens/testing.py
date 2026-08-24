"""Deterministic mock-LLM handlers.

These produce typed, transcript-aware outputs without any paid API. They are
used by tests, CI, and local offline demos — never to fabricate production
evidence (synthetic output is clearly sourced by the caller).
"""

from __future__ import annotations

import re

from pydantic import BaseModel

from calllens.domain.sentiment import SentimentLabel
from calllens.domain.topics import Topic
from calllens.domain.transcript import SpeakerRole, Transcript
from calllens.providers.llm.mock import Handler, MockLLMProvider
from calllens.semantic.schemas import (
    CoachingOutput,
    DimensionScore,
    EvidenceCandidate,
    EvidenceCandidates,
    IntentOut,
    IntentOutput,
    OpportunitiesOutput,
    OpportunityOut,
    RiskOut,
    SentimentOutput,
    SpeakerSentimentOut,
    TopicOutput,
    TurningPointOut,
)

_DIMENSION_RE = re.compile(r"Dimension:\s*(.+)")
_PRIORITY = ["high", "medium", "low"]


def _content_score(dimension: str, transcript_text: str) -> float:
    """Deterministic content-based score for the mock scorer.

    Maps simple, observable transcript signals to a dimension score so the
    evaluation harness sees genuine (if crude) signal from the mock.
    """
    questions = transcript_text.count("?")
    words = transcript_text.split()
    text = " ".join(words)

    def _has(*needles: str) -> bool:
        return any(n in text for n in needles)

    base: float = 5.0
    if dimension == "discovery":
        base = 3.5 + min(6.0, questions * 1.2)
    elif dimension == "rapport":
        base = 7.0 if _has("thanks", "great", "good", "nice", "pleasure") else 4.0
    elif dimension == "credentialization":
        base = 7.5 if _has("our platform", "we serve", "we have", "our product") else 3.5
    elif dimension == "ecosystem":
        base = 7.0 if _has("integrates", "ecosystem", "partners", "crm", "stack") else 3.5
    elif dimension == "adaptability":
        base = 7.0 if _has("understand", "hear you", "makes sense", "i see") else 4.0
    elif dimension in {"adjacent_cross_sell", "future_cross_sell"}:
        base = 7.5 if _has("also", "add", "package", "premium", "analytics") else 3.0
    elif dimension == "upsell":
        base = 7.5 if _has("plan", "upgrade", "premium", "seats", "higher") else 3.0
    elif dimension == "customer_energy":
        base = 7.0 if _has("huge", "great", "interesting", "love") else 4.0
    elif dimension == "budget_alignment":
        base = 7.5 if _has("budget", "price", "cost", "thousand", "pricing") else 3.0
    return base


def default_mock_handlers(transcript: Transcript) -> dict[type[BaseModel], Handler]:
    """Build handlers bound to a specific transcript."""
    roles = transcript.speaker_roles()
    reps = [
        u for u in transcript.utterances if roles.get(u.speaker_id) == SpeakerRole.REPRESENTATIVE
    ]
    custs = [u for u in transcript.utterances if roles.get(u.speaker_id) == SpeakerRole.CUSTOMER]
    # Fall back to speaker order when roles are not yet assigned
    # (normalization happens inside the graph).
    if not reps or not custs:
        speaker_ids = list(dict.fromkeys(u.speaker_id for u in transcript.utterances))
        rep_id = speaker_ids[0] if speaker_ids else "rep"
        cust_id = speaker_ids[1] if len(speaker_ids) > 1 else "customer"
        reps = [u for u in transcript.utterances if u.speaker_id == rep_id]
        custs = [u for u in transcript.utterances if u.speaker_id == cust_id]
    else:
        rep_id = reps[0].speaker_id
        cust_id = custs[0].speaker_id
    duration = transcript.duration or (
        max((u.end_time or 0) for u in transcript.utterances) if transcript.utterances else 0
    )

    def _label(prompt: str, fallback: str) -> str:
        m = _DIMENSION_RE.search(prompt)
        return m.group(1).strip() if m else fallback

    def _evidence(prompt: str, schema: type[BaseModel]) -> BaseModel:
        label = _label(prompt, "behavior")
        positive = [
            EvidenceCandidate(
                start_time=u.start_time,
                speaker="representative",
                transcript_excerpt=u.text,
                explanation=f"Representative demonstrates '{label}' here.",
            )
            for u in reps[:2]
        ]
        negative = [
            EvidenceCandidate(
                start_time=u.start_time,
                speaker="customer",
                transcript_excerpt=u.text,
                explanation=f"Counter-evidence relevant to '{label}'.",
            )
            for u in custs[:1]
        ]
        return EvidenceCandidates(
            dimension=label, positive=positive, negative=negative, missing_behaviors=[]
        )

    def _score(prompt: str, schema: type[BaseModel]) -> BaseModel:
        label = _label(prompt, "unknown")
        transcript_text = prompt.split("Here is the transcript of the call", 1)[-1].lower()
        score = _content_score(label, transcript_text)
        return DimensionScore(
            dimension=label,
            score=round(min(9.9, max(1.0, score)), 1),
            confidence=0.85,
            reasoning=(
                f"Mock reasoning: deterministic content signals for "
                f"'{label}' (questions, keywords, pacing) support this score."
            ),
        )

    def _sentiment(prompt: str, schema: type[BaseModel]) -> BaseModel:
        seg = [
            {
                "speaker_id": rep_id,
                "start": 0.0,
                "end": duration,
                "sentiment": "positive",
                "score": 0.55,
                "confidence": 0.8,
            },
            {
                "speaker_id": cust_id,
                "start": 0.0,
                "end": duration,
                "sentiment": "positive",
                "score": 0.35,
                "confidence": 0.75,
            },
        ]
        return SentimentOutput(
            customer=SpeakerSentimentOut(
                speaker_id=cust_id,
                timeline=seg[1:],
                overall=SentimentLabel.POSITIVE,
                average_score=0.35,
            ),
            representative=SpeakerSentimentOut(
                speaker_id=rep_id,
                timeline=seg[:1],
                overall=SentimentLabel.POSITIVE,
                average_score=0.55,
            ),
            turning_points=[
                TurningPointOut(
                    timestamp=min(duration, 12.0),
                    from_sentiment=SentimentLabel.NEUTRAL,
                    to_sentiment=SentimentLabel.POSITIVE,
                    trigger="mock",
                )
            ],
            engagement=0.7,
            frustration=0.1,
            enthusiasm=0.5,
            uncertainty=0.2,
            objection_intensity=0.3,
        )

    def _topics(prompt: str, schema: type[BaseModel]) -> BaseModel:
        topics = [
            Topic(
                topic="discovery",
                start_time=5.0,
                end_time=20.0,
                sentiment=SentimentLabel.NEUTRAL,
                confidence=0.8,
            ),
            Topic(
                topic="pricing",
                start_time=40.0,
                end_time=50.0,
                sentiment=SentimentLabel.POSITIVE,
                confidence=0.75,
            ),
        ]
        return TopicOutput(topics=topics)

    def _intents(prompt: str, schema: type[BaseModel]) -> BaseModel:
        return IntentOutput(
            intents=[
                IntentOut(
                    type="buying_intent",
                    description="Customer asks about pricing and platform fit.",
                    confidence=0.85,
                    evidence_timestamps=[u.start_time for u in custs[:1]],
                ),
                IntentOut(
                    type="objection",
                    description="Customer raises revenue impact concern.",
                    confidence=0.7,
                    evidence_timestamps=[u.start_time for u in custs[1:2]],
                ),
            ]
        )

    def _opportunities(prompt: str, schema: type[BaseModel]) -> BaseModel:
        ts = [u.start_time for u in reps[:1]]
        return OpportunitiesOutput(
            opportunities=[
                OpportunityOut(
                    type="cross_sell",
                    confidence=0.8,
                    description="Customer needs fulfillment automation.",
                    product_context="automation platform",
                    evidence_timestamps=ts,
                )
            ],
            risks=[
                RiskOut(
                    type="unresolved_concern",
                    confidence=0.6,
                    description="Budget fit not fully validated.",
                    evidence_timestamps=[u.start_time for u in custs[:1]],
                )
            ],
        )

    def _coaching(prompt: str, schema: type[BaseModel]) -> BaseModel:
        ts = [u.start_time for u in reps[:1]]
        return CoachingOutput(
            recommendations=[
                {
                    "title": "Establish business impact before positioning",
                    "priority": "high",
                    "recommendation": (
                        f"At {ts[0]:.0f}s you moved into the demo without "
                        f"quantifying the customer's revenue impact."
                    ),
                    "rationale": "Impact quantification strengthens urgency and budget alignment.",
                    "evidence_timestamps": ts,
                    "suggested_phrasing": (
                        '"What impact are those delays having on your customers or revenue?"'
                    ),
                }
            ]
        )

    return {
        EvidenceCandidates: _evidence,
        DimensionScore: _score,
        SentimentOutput: _sentiment,
        TopicOutput: _topics,
        IntentOutput: _intents,
        OpportunitiesOutput: _opportunities,
        CoachingOutput: _coaching,
    }


def build_mock_llm(transcript: Transcript) -> MockLLMProvider:
    """A fully-wired mock LLM provider for offline analysis."""
    return MockLLMProvider(default_mock_handlers(transcript))
