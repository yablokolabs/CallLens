"""Call lifecycle endpoints."""

from __future__ import annotations

import uuid
from contextlib import suppress

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from calllens.api.deps import AppState
from calllens.api.service import AnalysisService
from calllens.domain.report import AnalysisStatus, CallReport
from calllens.ingest.parsers import (
    TranscriptParseError,
    parse_transcript_json,
    parse_transcript_text,
)
from calllens.storage.base import RecordNotFound

router = APIRouter(prefix="/api/v1/calls", tags=["calls"])

AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".webm", ".aac"}


def _app(request: Request) -> AppState:
    return request.app.state.calllens


def _service(state: AppState) -> AnalysisService:
    return state.service


@router.post("")
async def create_call(
    request: Request,
    file: UploadFile | None = File(default=None),
    transcript_source: str | None = Form(default=None),
    rubric: str = Form(default="consultative_sales"),
) -> dict:
    """Upload a recording or transcript and (optionally) start analysis."""
    state = _app(request)
    call_id = str(uuid.uuid4())
    filename = file.filename if file else None
    await state.repository.create_call(
        call_id,
        organization_id=state.organization_id,
        filename=filename,
        status=AnalysisStatus.UPLOADED.value,
    )

    transcript = None
    audio: bytes | None = None
    if transcript_source:
        try:
            transcript = _parse_transcript_source(transcript_source)
        except TranscriptParseError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    elif file is not None:
        suffix = "." + (file.filename or "").rsplit(".", 1)[-1].lower()
        data = await file.read()
        if suffix in {".json"}:
            try:
                transcript = parse_transcript_json(data.decode("utf-8"))
            except TranscriptParseError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
        elif suffix in {".txt"}:
            try:
                transcript = parse_transcript_text(data.decode("utf-8"))
            except TranscriptParseError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
        elif (
            suffix in AUDIO_EXTENSIONS
            or file.content_type
            and file.content_type.startswith("audio/")
        ):
            audio = data
        else:
            raise HTTPException(
                status_code=400, detail=f"unsupported file type: {suffix or 'unknown'}"
            )

    if transcript is None and audio is None:
        raise HTTPException(
            status_code=400, detail="provide a transcript, transcript_source, or audio file"
        )

    rubric_model = state.rubrics.get(rubric) if rubric else None
    if not rubric_model:
        raise HTTPException(status_code=404, detail=f"rubric '{rubric}' not found")

    run_id = await _run_analysis(state, call_id, transcript, audio, rubric_model)
    return {"id": call_id, "run_id": run_id, "status": AnalysisStatus.UPLOADED.value}


async def _run_analysis(
    state: AppState, call_id: str, transcript, audio: bytes | None, rubric_model
) -> str:
    run_id = str(uuid.uuid4())
    if state.settings.calls_analyze_sync:
        await state.service.analyze(
            call_id,
            transcript,
            rubric_model,
            organization_id=state.organization_id,
            audio=audio,
        )
        return run_id

    async def job() -> None:
        await state.service.analyze(
            call_id,
            transcript,
            rubric_model,
            organization_id=state.organization_id,
            audio=audio,
        )

    await state.job_queue.submit(call_id, job)
    return run_id


def _parse_transcript_source(source: str):
    if source.lstrip().startswith(("{", "[")):
        return parse_transcript_json(source)
    return parse_transcript_text(source)


@router.get("")
async def list_calls(request: Request) -> list[dict]:
    state = _app(request)
    return await state.repository.list_calls(organization_id=state.organization_id)


@router.get("/{call_id}")
async def get_call(request: Request, call_id: str) -> dict:
    state = _app(request)
    try:
        return await state.repository.get_call(call_id, organization_id=state.organization_id)
    except RecordNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{call_id}/analyze")
async def analyze_call(request: Request, call_id: str, payload: dict | None = None) -> dict:
    """Trigger (re-)analysis for an existing call using the provided transcript."""
    state = _app(request)
    try:
        await state.repository.get_call(call_id, organization_id=state.organization_id)
    except RecordNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    rubric_name = (payload or {}).get("rubric_name", "consultative_sales")
    rubric_model = state.rubrics.get(rubric_name)
    if not rubric_model:
        raise HTTPException(status_code=404, detail=f"rubric '{rubric_name}' not found")

    transcript = None
    audio = None
    with suppress(RecordNotFound):
        transcript = await state.repository.get_transcript(
            call_id, organization_id=state.organization_id
        )
    if transcript is None:
        raise HTTPException(
            status_code=400, detail="no transcript stored for this call; upload one first"
        )

    run_id = await _run_analysis(state, call_id, transcript, audio, rubric_model)
    return {"id": call_id, "run_id": run_id}


@router.get("/{call_id}/analysis")
async def get_analysis(request: Request, call_id: str) -> CallReport:
    state = _app(request)
    try:
        return await state.repository.get_report(call_id, organization_id=state.organization_id)
    except RecordNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{call_id}/transcript")
async def get_transcript(request: Request, call_id: str):
    state = _app(request)
    try:
        return await state.repository.get_transcript(call_id, organization_id=state.organization_id)
    except RecordNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{call_id}")
async def delete_call(request: Request, call_id: str) -> dict:
    """Delete a call and all associated data (privacy/retention policy)."""
    state = _app(request)
    try:
        await state.repository.get_call(call_id, organization_id=state.organization_id)
    except RecordNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await state.repository.delete_call(call_id, organization_id=state.organization_id)
    return {"deleted": call_id}
