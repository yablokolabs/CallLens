"""Transcript-level escalation supplement — demo determinism without mocks.

The CallReport's risks/sentiment are mock-generated and not keyword-aware.
For demo reliability we also scan the raw transcript text when available.
This keeps ESCALATE deterministic even with mock providers (mocks always
return frustration 0.1 and generic risks).
"""

from __future__ import annotations

import re

_CHURN_RE = re.compile(
    r"\b(cancel|cancellation|churn|terminate|leaving|leave us|switching to|going with|canceling)\b",
    re.I,
)
_ANGER_RE = re.compile(r"\b(unacceptable|furious|angry|disgusted|never again|worst|outage|lost data)\b", re.I)


def transcript_has_escalation(transcript_text: str) -> tuple[bool, str, float]:
    low = transcript_text.lower()
    if _CHURN_RE.search(low):
        return True, "Customer explicitly indicated intent to leave / cancel (transcript)", 0.94
    if _ANGER_RE.search(low) and ("cancel" in low or "churn" in low or "unhappy" in low):
        return True, "Serious customer dissatisfaction with churn signal (transcript)", 0.90
    return False, "", 0.0
