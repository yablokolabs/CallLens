"""API behavior tests (TestClient, all providers mocked)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from calllens.api import create_app


@pytest.fixture
def client(settings, mock_speech, mock_llm, repository):
    app = create_app(
        settings=settings,
        repository=repository,
        speech=mock_speech,
        llm=mock_llm,
        rubrics_dir="rubrics",
    )
    with TestClient(app) as c:
        yield c


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_openapi_docs(client):
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    paths = resp.json()["paths"]
    assert "/api/v1/calls" in paths
    assert "/api/v1/rubrics" in paths
    assert "/api/v1/evals/run" in paths


def test_rubric_list(client):
    resp = client.get("/api/v1/rubrics")
    assert resp.status_code == 200
    names = [r["name"] for r in resp.json()]
    assert "consultative_sales" in names
    assert "customer_support" in names


def test_rubric_validate_valid(client):
    payload = {
        "name": "custom",
        "version": "1.0",
        "dimensions": {"empathy": {"label": "Empathy", "weight": 1.0}},
    }
    resp = client.post("/api/v1/rubrics/validate", json=payload)
    assert resp.status_code == 200
    assert resp.json()["valid"] is True


def test_rubric_validate_invalid_weights(client):
    payload = {
        "name": "custom",
        "version": "1.0",
        "dimensions": {"a": {"label": "A", "weight": 0.5}},
    }
    resp = client.post("/api/v1/rubrics/validate", json=payload)
    assert resp.json()["valid"] is False


def test_create_and_analyze_call_from_text(client):
    transcript = (
        "00:00 REP: Hi! What is your biggest challenge?\n"
        "00:05 CUSTOMER: Our fulfillment is slow.\n"
        "00:10 REP: We can help with that."
    )
    resp = client.post(
        "/api/v1/calls",
        data={"transcript_source": transcript, "rubric": "consultative_sales"},
    )
    assert resp.status_code == 200
    call_id = resp.json()["id"]

    # Wait for the background job to finish, then fetch the analysis.
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_wait_for_analysis(client.app, call_id))
    finally:
        loop.close()

    analysis = client.get(f"/api/v1/calls/{call_id}/analysis")
    assert analysis.status_code == 200
    body = analysis.json()
    assert body["status"] == "COMPLETED"
    assert len(body["rubric_scores"]) == 10
    assert body["overall_score"] > 0


async def _wait_for_analysis(app, call_id, timeout: float = 15.0):
    import asyncio
    import time

    repo = app.state.calllens.repository
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        call = await repo.get_call(call_id)
        if call["status"] == "COMPLETED":
            return
        await asyncio.sleep(0.1)
    raise AssertionError(f"analysis did not complete for {call_id}")


def test_upload_audio_uses_mock_speech(client):
    resp = client.post(
        "/api/v1/calls",
        files={"file": ("call.mp3", b"fake-audio-bytes", "audio/mpeg")},
        data={"rubric": "consultative_sales"},
    )
    assert resp.status_code == 200


def test_upload_rejects_bad_extension(client):
    resp = client.post(
        "/api/v1/calls",
        files={"file": ("notes.docx", b"nope", "application/octet-stream")},
    )
    assert resp.status_code == 400


def test_get_missing_call_404(client):
    resp = client.get("/api/v1/calls/does-not-exist")
    assert resp.status_code == 404


def test_delete_call(client):
    resp = client.post(
        "/api/v1/calls",
        data={"transcript_source": "00:00 REP: Hi\n00:05 CUSTOMER: Hello"},
    )
    call_id = resp.json()["id"]
    delete_resp = client.delete(f"/api/v1/calls/{call_id}")
    assert delete_resp.status_code == 200
    assert client.get(f"/api/v1/calls/{call_id}").status_code == 404


def test_custom_rubric_roundtrip(client):
    payload = {
        "name": "my_rubric",
        "version": "1.0",
        "dimensions": {
            "empathy": {"label": "Empathy", "weight": 0.6},
            "speed": {"label": "Speed", "weight": 0.4},
        },
    }
    resp = client.post("/api/v1/rubrics", json=payload)
    assert resp.status_code == 200
    assert client.get("/api/v1/rubrics/my_rubric").status_code == 200


def test_rep_analytics_empty(client):
    resp = client.get("/api/v1/reps/rep-1/analytics")
    assert resp.status_code == 200
    assert resp.json()["calls_analyzed"] == 0


def test_evals_run(client):
    resp = client.post(
        "/api/v1/evals/run", json={"scenarios": ["short_call", "excellent_salesperson"]}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["overall_mae"] >= 0
    assert len(body["runs"]) == 2
