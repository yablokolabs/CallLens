"""Synthetic demo calls for CallLens Coach (DEMO_MODE).

Three deterministic scenarios (conversation-intelligence fixtures):
  A — healthy call    → NO_ACTION  (balanced talk, good discovery, clear next step)
  B — coaching needed → COACH      (rep dominates, misses discovery, jumps to solution)
  C — human escalation→ ESCALATE   (churn/cancellation signal, manager review)

Each returns a transcript string + rep_id + expected decision so the demo,
tests, and seeding can all share the same source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass

from calllens.coach.history import HistoryRecord

DEMO_REPS = {
    "healthy": "rep_sarah",
    "coaching": "rep_daniel",
    "escalation": "rep_maya",
}

DEMO_CALL_IDS = {
    "healthy": "demo-sarah-acme",
    "coaching": "demo-daniel-northstar",
    "escalation": "demo-maya-contoso",
}


@dataclass(frozen=True)
class DemoCall:
    id: str
    scenario: str  # healthy | coaching | escalation
    title: str
    company: str
    rep_id: str
    rep_name: str
    expected_decision: str  # NO_ACTION | COACH | ESCALATE
    transcript: str


def _transcript_healthy() -> str:
    # Balanced talk, good discovery (many ? handoffs/impact), credentials+
    # ecosystem keywords so credentialization/ecosystem score high, rapport warm.
    return """\
00:00 REP: Hi Sarah, thanks for taking the time today. How is Acme thinking about onboarding?
00:12 CUSTOMER: We are growing and onboarding is becoming a bottleneck — mostly handoffs between teams.  # noqa: E501
00:28 REP: Thanks for sharing that, Sarah — that makes sense. Can you describe where the handoff breaks down today?  # noqa: E501
00:38 CUSTOMER: New hires wait on access and shadow sessions; managers are stretched.
00:52 REP: I hear you, that sounds challenging. What impact does that have on time-to-productivity?
01:04 CUSTOMER: About two weeks longer than we want, and it affects early retention.
01:18 REP: Understood. What would a good outcome look like in the next quarter?
01:30 CUSTOMER: Shorten ramp to under a week and give managers a clear checklist.
01:44 REP: That helps. Our platform handles that end-to-end — we serve teams at your scale and our product integrates with your stack. Teams using a structured ramp and checklist integration have cut ramp by 40%. Would a pilot with your onboarding checklist make sense?  # noqa: E501
02:02 CUSTOMER: Yes, that aligns with our budget for this quarter.
02:14 REP: Great — I will send the pilot scope and success criteria by tomorrow. Does Thursday work to review?  # noqa: E501
02:28 CUSTOMER: Thursday works. Thank you — this has been great.
"""


def _transcript_coaching() -> str:
    return """\
00:00 REP: Northstar is going to love this. Let me show the platform — it does everything.
00:14 CUSTOMER: Before we dive in, we have a specific issue around renewal forecasting.
00:22 REP: You will see — the dashboard here shows pipeline, forecast, and our AI predictions.
00:38 CUSTOMER: Our concern is that renewals are slipping because handoffs are missed.
00:48 REP: And here is pricing — we have three tiers and can close this quarter.
01:02 CUSTOMER: I mentioned forecasting — we need to understand how you address missed handoffs.
01:14 REP: The premium tier adds analytics and automation. I can add that today.
01:28 CUSTOMER: We were hoping to discuss the underlying cause first.
01:36 REP: I will send the order form — the analytics module will solve it.
01:48 CUSTOMER: We need a discovery step before any commitment.
"""


def _transcript_escalation() -> str:
    return """\
00:00 REP: Hi Maya, checking in on the Contoso rollout. How are things?
00:10 CUSTOMER: Honestly, we are very unhappy. The last release caused an outage and our team lost data.  # noqa: E501
00:26 REP: I understand that is frustrating. Can we look at what happened?
00:36 CUSTOMER: We have had three incidents this month. We are considering cancellation if this is not resolved.  # noqa: E501
00:52 REP: I hear you. Let me get the right people involved.
01:02 CUSTOMER: We need a formal review and a corrective plan, or we will churn. This is unacceptable.  # noqa: E501
01:18 REP: We will escalate this immediately and I will have our manager join.
01:28 CUSTOMER: Please have them contact us today. We are evaluating alternatives.
"""


def build_demo_calls() -> list[DemoCall]:
    return [
        DemoCall(
            id=DEMO_CALL_IDS["healthy"],
            scenario="healthy",
            title="Acme Corp — discovery + next step",
            company="Acme Corp",
            rep_id=DEMO_REPS["healthy"],
            rep_name="Sarah",
            expected_decision="NO_ACTION",
            transcript=_transcript_healthy(),
        ),
        DemoCall(
            id=DEMO_CALL_IDS["coaching"],
            scenario="coaching",
            title="Northstar — missed discovery, talk-heavy",
            company="Northstar",
            rep_id=DEMO_REPS["coaching"],
            rep_name="Daniel",
            expected_decision="COACH",
            transcript=_transcript_coaching(),
        ),
        DemoCall(
            id=DEMO_CALL_IDS["escalation"],
            scenario="escalation",
            title="Contoso — churn risk, serious dissatisfaction",
            company="Contoso",
            rep_id=DEMO_REPS["escalation"],
            rep_name="Maya",
            expected_decision="ESCALATE",
            transcript=_transcript_escalation(),
        ),
    ]


def build_history_seeds() -> dict[str, list[HistoryRecord]]:
    """5-call history windows that make coaching vs NO_ACTION gating visible.

    Daniel has a repeated discovery/talk pattern so COACH is warranted on the
    next call. Sarah's history is healthy so NO_ACTION stays NO_ACTION.
    """
    return {
        DEMO_REPS["coaching"]: [
            HistoryRecord(
                call_id="hist-daniel-1",
                decision="COACH",
                worst_dimension="discovery",
                worst_score=3.8,
                discovery_low=True,
            ),
            HistoryRecord(
                call_id="hist-daniel-2",
                decision="COACH",
                worst_dimension="discovery",
                worst_score=4.1,
                discovery_low=True,
            ),
            HistoryRecord(
                call_id="hist-daniel-3",
                decision="NO_ACTION",
                worst_dimension="rapport",
                worst_score=6.2,
            ),
            HistoryRecord(
                call_id="hist-daniel-4",
                decision="COACH",
                worst_dimension="discovery",
                worst_score=3.9,
                discovery_low=True,
                high_talk=True,
                rep_talk_ratio=0.79,
            ),
            HistoryRecord(
                call_id="hist-daniel-5",
                decision="COACH",
                worst_dimension="adaptability",
                worst_score=4.4,
                discovery_low=True,
            ),
        ],
        DEMO_REPS["healthy"]: [
            HistoryRecord(
                call_id="hist-sarah-1",
                decision="NO_ACTION",
                worst_dimension="rapport",
                worst_score=7.2,
            ),
            HistoryRecord(
                call_id="hist-sarah-2",
                decision="NO_ACTION",
                worst_dimension="discovery",
                worst_score=6.8,
            ),
            HistoryRecord(
                call_id="hist-sarah-3",
                decision="NO_ACTION",
                worst_dimension="adaptability",
                worst_score=7.0,
            ),
            HistoryRecord(
                call_id="hist-sarah-4",
                decision="NO_ACTION",
                worst_dimension="ecosystem",
                worst_score=6.5,
            ),
            HistoryRecord(
                call_id="hist-sarah-5",
                decision="NO_ACTION",
                worst_dimension="rapport",
                worst_score=7.1,
            ),
        ],
        DEMO_REPS["escalation"]: [
            HistoryRecord(
                call_id="hist-maya-1",
                decision="NO_ACTION",
                worst_dimension="rapport",
                worst_score=6.4,
            ),
            HistoryRecord(
                call_id="hist-maya-2",
                decision="COACH",
                worst_dimension="adaptability",
                worst_score=4.8,
            ),
        ],
    }
