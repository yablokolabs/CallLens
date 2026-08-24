"""End-to-end integration through the service layer (no network)."""

from __future__ import annotations

import pytest

from calllens.api.service import AnalysisService


@pytest.mark.asyncio
async def test_service_analyze_persists_report(
    settings, transcript, rubric, mock_speech, mock_llm, repository
):
    await repository.create_call("e2e-1")
    service = AnalysisService(repository, mock_speech, mock_llm, settings)
    run_id = await service.analyze("e2e-1", transcript, rubric)
    assert run_id
    report = await repository.get_report("e2e-1")
    assert report.status.value == "COMPLETED"
    assert report.overall_score > 0
    stored = await repository.get_transcript("e2e-1")
    assert len(stored.utterances) == len(transcript.utterances)
    call = await repository.get_call("e2e-1")
    assert call["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_service_persists_failure(settings, transcript, rubric, mock_speech, repository):
    class ExplodingLLM:
        async def completion(self, prompt, *, system=None):
            raise RuntimeError("boom")

        async def structured_completion(self, prompt, schema, *, system=None):
            raise RuntimeError("boom")

    await repository.create_call("e2e-fail")
    service = AnalysisService(repository, mock_speech, ExplodingLLM(), settings)
    with pytest.raises(RuntimeError, match="boom"):
        await service.analyze("e2e-fail", transcript, rubric)
    call = await repository.get_call("e2e-fail")
    assert call["status"] == "FAILED"


@pytest.mark.asyncio
async def test_sdk_client_calls_api(settings, mock_speech, mock_llm, repository):
    """SDK against a live TestClient-backed ASGI app."""
    import httpx

    from calllens.api import create_app

    app = create_app(
        settings=settings,
        repository=repository,
        speech=mock_speech,
        llm=mock_llm,
        rubrics_dir="rubrics",
    )
    transport = httpx.ASGITransport(app=app)
    from calllens.sdk.client import CallLens

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        from calllens.sdk.client import Call

        client = CallLens(base_url="http://test")
        client._http = http  # noqa: SLF001
        calls = await client.calls.list()
        assert isinstance(calls, list)
        await repository.create_call("sdk-1")
        call = Call(client, "sdk-1")
        await call.delete()
        from calllens.sdk.client import CallLensError

        with pytest.raises(CallLensError):
            await client.calls.get("sdk-1")
