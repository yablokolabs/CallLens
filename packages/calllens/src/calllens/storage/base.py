"""Persistence abstraction.

Business logic depends only on this Protocol so local development (memory or
SQLite) and production (PostgreSQL/Supabase) share the same API surface.
Multi-tenancy is designed in from day one: every record carries an
``organization_id`` and repository methods scope by it.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from calllens.domain.report import AnalysisRun, CallReport
from calllens.domain.transcript import Transcript


class RecordNotFound(LookupError):
    """Raised when a requested record does not exist."""


@runtime_checkable
class Repository(Protocol):
    """Store and retrieve calls and their analyses."""

    async def create_call(
        self,
        call_id: str,
        *,
        organization_id: str | None = None,
        filename: str | None = None,
        status: str = "UPLOADED",
        metadata: dict | None = None,
    ) -> dict:
        """Register a call and return its record."""
        ...

    async def get_call(self, call_id: str, *, organization_id: str | None = None) -> dict:
        """Fetch a call record; raises RecordNotFound."""
        ...

    async def list_calls(self, *, organization_id: str | None = None) -> list[dict]:
        """List call records (newest first)."""
        ...

    async def update_call_status(self, call_id: str, status: str) -> None:
        """Persist a status transition (UPLOADED → TRANSCRIBING → ...)."""
        ...

    async def save_report(self, call_id: str, report: CallReport) -> None:
        """Persist a completed analysis report."""
        ...

    async def save_transcript(self, call_id: str, transcript: Transcript) -> None:
        """Persist the normalized transcript for a call."""
        ...

    async def get_transcript(
        self, call_id: str, *, organization_id: str | None = None
    ) -> Transcript:
        """Fetch the stored transcript; raises RecordNotFound."""
        ...

    async def get_report(self, call_id: str, *, organization_id: str | None = None) -> CallReport:
        """Fetch the latest report for a call; raises RecordNotFound."""
        ...

    async def delete_call(self, call_id: str, *, organization_id: str | None = None) -> None:
        """Delete a call and all associated data."""
        ...

    async def save_analysis_run(self, run: AnalysisRun) -> None:
        """Persist an analysis run (audit trail + state transitions)."""
        ...

    async def get_analysis_run(self, run_id: str) -> AnalysisRun:
        """Fetch an analysis run; raises RecordNotFound."""
        ...
