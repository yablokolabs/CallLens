"""Prompt templates.

Every prompt is versioned so analyses remain auditable: the prompt version is
recorded with each analysis (see ``ModelIdentity.prompt_version``).
"""

from __future__ import annotations

PROMPT_VERSION = "1.0"

_TRANSCRIPT_BLOCK = """\
Here is the transcript of the call (timestamps in MM:SS):

{transcript}
"""


def sentiment_prompt(transcript: str) -> str:
    return (
        _TRANSCRIPT_BLOCK.format(transcript=transcript)
        + """
Analyze the sentiment of this conversation longitudinally, per speaker.
Produce:
- a timeline of sentiment segments per speaker with start/end seconds, a
  sentiment label, a score in [-1, 1], and a confidence in [0, 1]
- the overall sentiment and average score per speaker
- turning points where sentiment direction changed materially
- engagement, frustration, enthusiasm, uncertainty, and objection intensity,
  each in [0, 1]
Base every inference on observable behavior in the transcript.
Return the result as valid JSON matching the requested schema.
"""
    )


def topics_prompt(transcript: str) -> str:
    return (
        _TRANSCRIPT_BLOCK.format(transcript=transcript)
        + """
Extract the distinct topics discussed, in order. For each topic return:
- a short lowercase topic name
- start_time and end_time (seconds) bounding the discussion
- the dominant sentiment during the topic
- a confidence in [0, 1]
Return the result as valid JSON matching the requested schema.
"""
    )


def intents_prompt(transcript: str) -> str:
    return (
        _TRANSCRIPT_BLOCK.format(transcript=transcript)
        + """
Detect conversational intents such as: objection, buying signal, budget
mention, decision-maker mention, purchase timeline, competitor mention,
follow-up commitment, next action.
For each intent return type, a short description, confidence in [0, 1], and
the timestamps (seconds) of the utterances that support it.
Return the result as valid JSON matching the requested schema.
"""
    )


def evidence_prompt(transcript: str, dimension_label: str, dimension_description: str) -> str:
    return (
        _TRANSCRIPT_BLOCK.format(transcript=transcript)
        + f"""
You are evaluating one behavioral dimension of a call.

Dimension: {dimension_label}
Definition: {dimension_description}

Extract candidate evidence:
- positive: excerpts that demonstrate the behavior, with the timestamp
  (seconds), speaker side ("representative" or "customer"), the exact excerpt
  text, and why it demonstrates the behavior
- negative: excerpts that contradict the behavior or show its absence
- missing_behaviors: behaviors the representative never performed that the
  dimension expects

Use only actual content from the transcript. Do not invent quotes.
Return the result as valid JSON matching the requested schema.
"""
    )


def score_prompt(
    transcript: str,
    dimension_label: str,
    dimension_description: str,
    positive_evidence: str,
    negative_evidence: str,
    missing_behaviors: str,
) -> str:
    return (
        _TRANSCRIPT_BLOCK.format(transcript=transcript)
        + f"""
Score the following behavioral dimension of this call.

Dimension: {dimension_label}
Definition: {dimension_description}

Verified positive evidence:
{positive_evidence}

Verified negative evidence:
{negative_evidence}

Missing behaviors:
{missing_behaviors}

Return:
- score: a number from 0 to 10 (use one decimal place)
- confidence: a number from 0 to 1 reflecting how strongly the evidence
  supports the score
- reasoning: 1-3 sentences grounded in the evidence above

Return the result as valid JSON matching the requested schema.
"""
    )


def rescore_prompt(
    transcript: str,
    dimension_label: str,
    previous_score: float,
    previous_reasoning: str,
    instruction: str,
) -> str:
    return (
        _TRANSCRIPT_BLOCK.format(transcript=transcript)
        + f"""
Re-evaluate the behavioral dimension "{dimension_label}".

Previous score: {previous_score}
Previous reasoning: {previous_reasoning}

Reviewer instruction: {instruction}

Return a corrected score (0-10), confidence (0-1), and updated reasoning.
Return the result as valid JSON matching the requested schema.
"""
    )


def opportunities_prompt(transcript: str) -> str:
    return (
        _TRANSCRIPT_BLOCK.format(transcript=transcript)
        + """
Detect commercial opportunities and risks in this call.
Opportunity types: upsell, cross_sell, budget_signal, buying_intent,
purchase_timeline, decision_maker.
Risk types: objection, unresolved_concern, competitor, missed_follow_up, other.
For each item return type, confidence in [0, 1], a short description,
optional product context, and the supporting timestamps (seconds).
Only include items with real supporting evidence.
Return the result as valid JSON matching the requested schema.
"""
    )


def coaching_prompt(transcript: str, rubric_scores: str) -> str:
    return (
        _TRANSCRIPT_BLOCK.format(transcript=transcript)
        + f"""
Write evidence-backed coaching recommendations for the representative based
on this rubric evaluation:

{rubric_scores}

For each recommendation:
- title: short and specific
- priority: high | medium | low
- recommendation: concrete, referencing what happened at specific timestamps
- rationale: why this matters
- evidence_timestamps: the timestamps (seconds) that support it
- suggested_phrasing: an example of what the representative could say instead
  (optional)

Never give generic advice like "ask more questions" without referencing
actual moments in the call.
Return the result as valid JSON matching the requested schema.
"""
    )
