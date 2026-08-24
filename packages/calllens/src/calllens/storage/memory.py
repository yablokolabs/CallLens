"""In-memory repository (default for tests and single-process demos)."""

from __future__ import annotations

from calllens.domain.report import AnalysisRun, CallReport
from calllens.domain.transcript import Transcript
from calllens.storage.base import RecordNotFound


class InMemoryRepository:
    """Thread-safe-ish in-memory store. Not for production persistence."""

    def __init__(self) -> None:
        self._calls: dict[str, dict] = {}
        self._reports: dict[str, CallReport] = {}
        self._transcripts: dict[str, Transcript] = {}
        self._runs: dict[str, AnalysisRun] = {}

    async def create_call(
        self,
        call_id: str,
        *,
        organization_id: str | None = None,
        filename: str | None = None,
        status: str = "UPLOADED",
        metadata: dict | None = None,
    ) -> dict:
        record = {
            "id": call_id,
            "organization_id": organization_id,
            "filename": filename,
            "status": status,
            "metadata": metadata or {},
        }
        self._calls[call_id] = record
        return record

    async def get_call(self, call_id: str, *, organization_id: str | None = None) -> dict:
        record = self._calls.get(call_id)
        if record is None:
            raise RecordNotFound(f"call {call_id} not found")
        return record

    async def list_calls(self, *, organization_id: str | None = None) -> list[dict]:
        calls = list(self._calls.values())
        if organization_id is not None:
            calls = [c for c in calls if c.get("organization_id") == organization_id]
        return sorted(calls, key=lambda c: str(c.get("created_at", "")), reverse=True)

    async def update_call_status(self, call_id: str, status: str) -> None:
        record = await self.get_call(call_id)
        record["status"] = status

    async def save_report(self, call_id: str, report: CallReport) -> None:
        self._reports[call_id] = report

    async def get_report(self, call_id: str, *, organization_id: str | None = None) -> CallReport:
        report = self._reports.get(call_id)
        if report is None:
            raise RecordNotFound(f"report for call {call_id} not found")
        return report

    async def save_transcript(self, call_id: str, transcript: Transcript) -> None:
        self._transcripts[call_id] = transcript

    async def get_transcript(
        self, call_id: str, *, organization_id: str | None = None
    ) -> Transcript:
        transcript = self._transcripts.get(call_id)
        if transcript is None:
            raise RecordNotFound(f"transcript for call {call_id} not found")
        return transcript

    async def delete_call(self, call_id: str, *, organization_id: str | None = None) -> None:
        self._calls.pop(call_id, None)
        self._reports.pop(call_id, None)
        self._transcripts.pop(call_id, None)

    async def save_analysis_run(self, run: AnalysisRun) -> None:
        self._runs[run.id] = run

    async def get_analysis_run(self, run_id: str) -> AnalysisRun:
        run = self._runs.get(run_id)
        if run is None:
            raise RecordNotFound(f"analysis run {run_id} not found")
        return run
