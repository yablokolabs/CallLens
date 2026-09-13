"""Coach API smoke tests (no network, mock providers)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from calllens.api import create_app
from calllens.coach.demo import build_demo_calls


@pytest.fixture
def client(settings, mock_speech, mock_llm, repository):
    # Use coach-friendly settings
    app = create_app(
        settings=settings,
        repository=repository,
        speech=mock_speech,
        llm=mock_llm,
        rubrics_dir="rubrics",
    )
    with TestClient(app) as c:
        yield c


def test_health_has_coach_fields(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "coach_provider" in body


def test_openapi_has_coach_routes(client):
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    paths = resp.json()["paths"]
    assert "/api/coach/summary" in paths
    assert "/api/coach/calls" in paths
    assert "/api/coach/calls/{call_id}" in paths
    assert "/api/coach/analyze" in paths
    assert "/api/coach/reps/{rep_id}/history" in paths


def test_coach_summary_and_seed(client):
    resp = client.get("/api/coach/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 18
    assert body["by_decision"] == {"NO_ACTION": 15, "COACH": 2, "ESCALATE": 1}

    seed = client.post("/api/coach/seed")
    assert seed.status_code == 200
    assert seed.json()["seeded"] == 3


def test_coach_list_and_get(client):
    calls = client.get("/api/coach/calls").json()
    assert len(calls) == 18
    # Deterministic hero decisions
    by_id = {c["call_id"]: c for c in calls}
    assert by_id["demo-sarah-acme"]["decision"] == "NO_ACTION"
    assert by_id["demo-daniel-northstar"]["decision"] == "COACH"
    assert by_id["demo-maya-contoso"]["decision"] == "ESCALATE"

    detail = client.get("/api/coach/calls/demo-daniel-northstar").json()
    assert detail["decision"] == "COACH"
    assert detail["confidence"] >= 0.8
    assert len(detail["evidence"]) >= 1
    assert detail["recommended_action"] is not None
    assert detail["human_review_required"] is False
    # Strands trace: check_escalation + evidence + history + action + Decision + Action
    assert len(detail["trace"]) == 6
    assert any("Strands requested" in s["step"] for s in detail["trace"])
    assert detail["history_context"] is not None

    esc = client.get("/api/coach/calls/demo-maya-contoso").json()
    assert esc["human_review_required"] is True
    assert esc["evidence"]


def test_coach_analyze_healthy_no_action(client):
    demo = build_demo_calls()[0]
    resp = client.post(
        "/api/coach/analyze", json={"transcript": demo.transcript, "rep_id": "rep_sarah"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["decision"] == "NO_ACTION"
    assert body["human_review_required"] is False


def test_coach_analyze_coaching(client):
    demo = build_demo_calls()[1]
    resp = client.post(
        "/api/coach/analyze", json={"transcript": demo.transcript, "rep_id": "rep_daniel"}
    )
    assert resp.status_code == 200
    assert resp.json()["decision"] == "COACH"


def test_coach_analyze_escalation(client):
    demo = build_demo_calls()[2]
    resp = client.post(
        "/api/coach/analyze", json={"transcript": demo.transcript, "rep_id": "rep_maya"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["decision"] == "ESCALATE"
    assert body["human_review_required"] is True


def test_coach_rep_history(client):
    resp = client.get("/api/coach/reps/rep_daniel/history")
    assert resp.status_code == 200
    body = resp.json()
    assert "pattern_counts" in body
    assert "note" in body
    assert body["rep_id"] == "rep_daniel"

    # Unknown rep returns empty history, not 404
    resp2 = client.get("/api/coach/reps/unknown-rep/history")
    assert resp2.status_code == 200
    assert resp2.json()["total_calls"] == 0


def test_coach_get_404(client):
    resp = client.get("/api/coach/calls/does-not-exist")
    assert resp.status_code == 404


def test_coach_analyze_rejects_empty(client):
    resp = client.post("/api/coach/analyze", json={"transcript": "   "})
    assert resp.status_code == 400


def test_coach_reset_clears_state(client):
    """Reset wipes seeded decisions; mock provider reseeds on next GET."""
    # Seed first
    assert client.get("/api/coach/summary").json()["total"] == 18
    # Reset — clean ack (no auto-reseed inside this response)
    resp = client.post("/api/coach/reset")
    assert resp.status_code == 200
    assert resp.json() == {"reset": True}
    # Mock provider auto-reseeds on next GET
    assert client.get("/api/coach/summary").json()["total"] == 18
